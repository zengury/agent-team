"""
需求契约验证 — 客户需求 → PRD → 代码 逐层追溯。

每一层产出完成后，自动核查：
1. 原始需求是否在 PRD 中有对应功能
2. PRD 功能是否在代码中有对应实现
3. 产出覆盖率报告

这是防止"客户说要门、PRD里没门、代码里没门"的最后防线。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Requirement:
    """从客户对话中提取的一条可验证需求."""
    id: str
    description: str
    source: str           # "transcript" | "analysis" 
    priority: str = "must"  # must | should | could
    category: str = ""    # "订单录入" | "库存管理" | "报表" etc
    
    # 验证状态
    in_prd: bool = False
    prd_feature: str = ""     # PRD中对应的功能描述
    in_code: bool = False
    code_evidence: str = ""   # 代码中的证据(file:line)


@dataclass
class CoverageReport:
    """覆盖率报告."""
    phase: str               # "prd" | "code" | "test" 
    agent: str
    total_requirements: int
    covered: int
    uncovered: list[Requirement]
    coverage_pct: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def passed(self) -> bool:
        return self.coverage_pct >= 70  # 70%覆盖率阈值


class ContractVerifier:
    """
    需求契约验证器。
    
    工作流:
    1. extract_requirements(transcript, analysis) → list[Requirement]
    2. verify_prd_coverage(prd_text) → CoverageReport
    3. verify_code_coverage(code_dir) → CoverageReport
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._requirements: list[Requirement] = []
        self._reports: list[CoverageReport] = []
        self._contract_path = workspace / "contract.json"

    # ── 需求提取 ───────────────────────────────────────

    def extract_requirements(self, transcript: str, tangseng_analysis: str = "",
                             llm_call: callable = None) -> list[Requirement]:
        """
        从客户对话和唐僧分析中提取结构化需求列表。
        
        优先使用LLM提取（更准确），降级使用关键词匹配。
        """
        if llm_call:
            try:
                prompt = f"""从以下客户对话中提取3-8条具体的、可验证的功能需求。
每条需求一行，格式: "类别: 具体需求描述"
类别从以下选: 订单录入, 生产与库存, 数据看板, 通知与通信, 人员管理, 客户管理, 系统集成

客户对话:
{transcript[:3000]}

分析:
{tangseng_analysis[:1000]}

需求清单:"""
                result = llm_call(prompt)
                # Parse LLM output
                for line in result.split('\n')[:10]:
                    line = line.strip()
                    if ':' in line and len(line) > 5:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            cat = self._categorize(parts[0])
                            self._requirements.append(Requirement(
                                id=f"R{len(self._requirements)+1:03d}",
                                description=parts[1].strip()[:120],
                                source="llm_extraction",
                                category=cat,
                                priority="must" if any(kw in parts[1] for kw in ["必须","自动","核心","订单"]) else "should",
                            ))
                if len(self._requirements) >= 3:
                    self._save_contract()
                    return self._requirements
            except Exception as e:
                logger.warning(f"LLM需求提取失败, 降级关键词: {e}")
        
        # 降级: 关键词匹配
        reqs = []
        idx = 0
        
        # 从 transcript 提取
        patterns = [
            r'(?:我想要|我需要|我希望|我想|我们要|我们想)([^。！\n]{6,60})',
            r'(?:问题是|痛点|最大问题是|最头疼)([^。！\n]{6,60})',
            r'(?:自动|不用|不要手动|不需要人工)([^。！\n]{6,60})',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, transcript):
                desc = match.group(1).strip()[:120]
                cat = self._categorize(desc)
                reqs.append(Requirement(
                    id=f"R{idx+1:03d}",
                    description=desc,
                    source="transcript",
                    category=cat,
                    priority="must" if any(kw in desc for kw in ["自动","不","错误","问题","丢失"]) else "should",
                ))
                idx += 1
        
        # 从唐僧分析提取功能建议
        if tangseng_analysis:
            for match in re.finditer(r'(?:开发|搭建|接入|实现|构建)([^。！\n]{8,60})', tangseng_analysis):
                desc = match.group(1).strip()[:120]
                if not any(r.description == desc for r in reqs):
                    reqs.append(Requirement(
                        id=f"R{idx+1:03d}",
                        description="需要" + desc,
                        source="analysis",
                        category=self._categorize(desc),
                        priority="should",
                    ))
                    idx += 1
        
        self._requirements = reqs
        self._save_contract()
        
        logger.info(f"提取了 {len(reqs)} 条需求")
        for r in reqs:
            logger.info(f"  {r.id} [{r.category}] {r.description[:80]}")
        
        return reqs

    def _categorize(self, text: str) -> str:
        """根据关键词分类需求."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["订单","接单","line","whatsapp","消息","消息","录入"]):
            return "订单录入"
        if any(kw in text_lower for kw in ["库存","备货","烘焙","烤","生产","排产"]):
            return "生产与库存"
        if any(kw in text_lower for kw in ["报表","看板","数据","销售","分析","统计"]):
            return "数据看板"
        if any(kw in text_lower for kw in ["通知","提醒","预警","确认","发送","消息"]):
            return "通知与通信"
        if any(kw in text_lower for kw in ["排班","员工","考勤","人"]):
            return "人员管理"
        return "其他"

    # ── PRD 覆盖率验证 ─────────────────────────────────

    def verify_prd_coverage(self, prd_text: str) -> CoverageReport:
        """
        检查PRD是否覆盖了所有需求。
        
        对每条需求，在PRD中搜索相关关键词，判断是否有对应功能。
        """
        uncovered = []
        covered_count = 0
        
        for req in self._requirements:
            # 提取需求中的关键词
            keywords = self._extract_keywords(req.description)
            
            # 在 PRD 中搜索
            prd_lower = prd_text.lower()
            matches = sum(1 for kw in keywords if kw.lower() in prd_lower)
            
            if matches >= 2:  # 至少匹配2个关键词
                req.in_prd = True
                req.prd_feature = f"PRD中发现 {matches} 个关键词匹配"
                covered_count += 1
            else:
                uncovered.append(req)
        
        report = CoverageReport(
            phase="prd",
            agent="bajie",
            total_requirements=len(self._requirements),
            covered=covered_count,
            uncovered=uncovered,
            coverage_pct=(covered_count / max(len(self._requirements), 1)) * 100,
        )
        self._reports.append(report)
        self._save_contract()
        return report

    # ── 代码覆盖率验证 ─────────────────────────────────

    def verify_code_coverage(self, code_dir: Path | None = None) -> CoverageReport:
        """
        检查代码是否实现了PRD中的功能。
        
        查看 src/ 目录中的 .py 文件，搜索功能关键词。
        """
        code_dir = code_dir or (self.workspace / "src")
        if not code_dir.exists():
            return CoverageReport(phase="code", agent="wukong", total_requirements=len(self._requirements), 
                                  covered=0, uncovered=self._requirements, coverage_pct=0)
        
        # 读取所有代码文件
        all_code = ""
        for py_file in code_dir.glob("**/*.py"):
            try:
                all_code += py_file.read_text() + "\n"
            except:
                pass
        
        uncovered = []
        covered_count = 0
        
        for req in self._requirements:
            if not req.in_prd:
                continue  # PRD都没覆盖，代码肯定没有
            
            keywords = self._extract_keywords(req.description)
            code_lower = all_code.lower()
            
            # 检查是否有对应的路由/函数/模型
            has_route = any(kw.lower() in code_lower for kw in keywords)
            
            # 额外检查: 是否有 POST/PUT/DELETE 方法（写入功能）
            has_write = any(method in all_code for method in ["POST", "PUT", "DELETE", "methods=['POST'"])
            
            if has_route:
                req.in_code = True
                req.code_evidence = f"代码中找到 {sum(1 for kw in keywords if kw.lower() in code_lower)} 个关键词"
                covered_count += 1
            elif "订单" in req.category and not has_write:
                req.code_evidence = "缺失: 没有POST端点，无法录入数据"
                uncovered.append(req)
            else:
                uncovered.append(req)
        
        report = CoverageReport(
            phase="code",
            agent="wukong",
            total_requirements=len([r for r in self._requirements if r.in_prd]),
            covered=covered_count,
            uncovered=uncovered,
            coverage_pct=(covered_count / max(len([r for r in self._requirements if r.in_prd]), 1)) * 100,
        )
        self._reports.append(report)
        self._save_contract()
        return report

    # ── 工具函数 ───────────────────────────────────────

    def _extract_keywords(self, text: str, max_kw: int = 5) -> list[str]:
        """从文本中提取关键词."""
        # 移除常见停用词
        stop_words = {"的","了","在","是","我","有","和","就","不","人","都","一","一个",
                      "上","也","很","到","说","要","去","你","会","着","没","看","好","自己",
                      "这","他","她","它","们","那","什么","怎么","如何","为什么","因为","所以"}
        words = re.findall(r'[\w\u4e00-\u9fff]{2,}', text)
        keywords = [w for w in words if w not in stop_words]
        return keywords[:max_kw]

    def _save_contract(self):
        """保存契约到磁盘."""
        data = {
            "requirements": [
                {
                    "id": r.id,
                    "description": r.description,
                    "category": r.category,
                    "priority": r.priority,
                    "in_prd": r.in_prd,
                    "in_code": r.in_code,
                }
                for r in self._requirements
            ],
            "reports": [
                {
                    "phase": rpt.phase,
                    "coverage_pct": rpt.coverage_pct,
                    "covered": rpt.covered,
                    "total": rpt.total_requirements,
                    "uncovered": [r.id for r in rpt.uncovered],
                }
                for rpt in self._reports
            ],
        }
        self._contract_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def get_summary(self) -> dict:
        """获取当前契约验证总结."""
        if not self._requirements:
            return {"status": "no_requirements", "message": "请先运行需求提取"}
        
        return {
            "total_requirements": len(self._requirements),
            "prd_coverage": next(
                (rpt.coverage_pct for rpt in reversed(self._reports) if rpt.phase == "prd"), 0
            ),
            "code_coverage": next(
                (rpt.coverage_pct for rpt in reversed(self._reports) if rpt.phase == "code"), 0
            ),
            "uncovered_critical": [
                r.description[:100] for r in self._requirements
                if not r.in_prd and r.priority == "must"
            ],
            "reports": [
                {"phase": rpt.phase, "coverage": f"{rpt.coverage_pct:.0f}%", "passed": rpt.passed}
                for rpt in self._reports
            ],
        }
