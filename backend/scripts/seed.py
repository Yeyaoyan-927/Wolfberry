"""初始化演示数据：用户 / 行情 / 知识库文档。

用法：python scripts/seed.py
"""
from __future__ import annotations

import datetime as dt
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import SessionLocal, create_all  # noqa: E402
from app.models.sys import ROLE_ADMIN, ROLE_BUYER, ROLE_SELLER, SysUser  # noqa: E402
from app.services import kb_service  # noqa: E402

random.seed(20261026)

USERS = [
    ("admin", "admin123", ROLE_ADMIN, "平台管理员", ""),
    ("seller1", "seller123", ROLE_SELLER, "中宁杞源合作社", "中宁杞源合作社"),
    ("seller2", "seller123", ROLE_SELLER, "青海诺木洪枸杞", "诺木洪枸杞种植合作社"),
    ("buyer1", "buyer123", ROLE_BUYER, "杭州佰味食品", "杭州佰味食品有限公司"),
]

DOC_GBT = """# 枸杞分级与术语标准（GB/T 18672 摘录）

5.1 术语与定义
5.1.1 霉变粒：因霉菌侵染使子叶变色、变质，失去食用价值的枸杞颗粒。
5.1.2 油果：干燥过程中因受热不均或返潮导致果皮呈油浸状、颜色明显加深发暗的枸杞颗粒。
5.1.3 不完善粒：破损粒、虫蚀粒以及形态明显不完整的枸杞颗粒。

5.2 质量等级
枸杞按感官与理化指标分为特优、特级、甲级、乙级四个等级，各等级应符合表 2 的规定。
5.2.1 特级：颗粒大小均匀，色泽一致，无明显霉变粒；破碎粒及不完善粒总量不超过 2.0%；霉变粒不大于 0.2%。
5.2.2 甲级：颗粒基本均匀，允许少量不完善粒；破碎粒及不完善粒总量不超过 5.0%；霉变粒不大于 0.5%。
5.2.3 乙级：不完善粒总量不超过 10.0%；霉变粒不大于 1.5%；超过 1.5% 的不得作为食用枸杞流通。

5.3 理化指标
5.3.1 水分：不大于 13.0%。
5.3.2 总糖（以葡萄糖计）：不小于 45.0%。
5.3.3 粒度要求按规格执行：180 粒/50g、220 粒/50g、280 粒/50g、380 粒/50g 等。

6.3 检验方法
6.3.1 水分按 GB 5009.3 规定的方法测定。
6.3.2 二氧化硫残留量按 GB 5009.34 规定的方法测定。
"""

DOC_RULES = """# 平台商品审核规则（外观维度）

1. 等级判定
平台依据卖家上传实拍图进行图像评估，综合缺陷率、霉变率、相对粒径给出建议等级：
1.1 特优：综合缺陷率不超过 1.0%，无霉变粒。
1.2 特级：综合缺陷率不超过 2.0%，霉变率不大于 0.2%。
1.3 甲级：综合缺陷率不超过 5.0%，霉变率不大于 0.5%。
1.4 乙级：综合缺陷率不超过 10.0%，霉变率不大于 1.5%。
1.5 任一指标不达标时按最差项定级；霉变率超过 1.5% 一票否决，不允许上架。

2. 等级差异标记
2.1 卖家自述等级与图像评估建议一致时，标记为绿色。
2.2 卖家自述等级高于评估建议 1 级时，标记为黄色，进入重点审核。
2.3 高于评估建议 2 级及以上时，标记为红色，默认建议驳回或改级。
2.4 评估置信度低于 0.45 时，评估建议不参与差异判定，由审核员人工判断。

3. 驳回与重提
3.1 驳回原因包括：等级高报、图片模糊、非实拍图、描述不符、价格异常、资质不全。
3.2 被驳回的商品可修改后重新提交，原审核记录保留。
3.3 已上架商品修改实拍图或自述等级后，需重新提交审核。
"""

DOC_STORAGE = """# 枸杞储存常见问题

问：干枸杞买回来怎么保存？
答：密封后置于阴凉干燥处（建议温度 20 摄氏度以下、相对湿度 60% 以下），避免阳光直射。

问：夏天高温高湿，枸杞容易返潮结块怎么办？
答：可分装成小袋冷冻保存（零下 18 摄氏度），取出后恢复至室温再开封，避免凝结水汽。

问：枸杞表面发粘是坏了吗？
答：轻度返潮结块挑散后尽快食用即可；若出现酒味、酸味或霉斑则不可食用。

问：拆封后能放多久？
答：常温密封建议 1 个月内食用完；冷藏 3 个月；冷冻 12 个月。

问：不同等级的枸杞口感有差异吗？
答：特优/特级果肉厚、甜度高，适合直接食用与礼盒；甲级、乙级更适合煮粥、泡水与食品加工。
"""


def seed_users(session) -> None:
    for username, password, role, name, org in USERS:
        from app.core.security import hash_password

        exists = session.query(SysUser).filter_by(username=username).first()
        if exists:
            print(f"  跳过用户 {username}（已存在）")
            continue
        session.add(
            SysUser(
                username=username,
                password_hash=hash_password(password),
                role=role,
                display_name=name,
                org_name=org,
            )
        )
        print(f"  用户 {username}（{role}）")
    session.commit()


def seed_market(session) -> None:
    from app.models.product import MarketQuote

    if session.query(MarketQuote).count() > 0:
        print("  跳过行情（已有数据）")
        return

    today = dt.date.today()
    specs = {
        ("宁杞5号", "特级", "中宁"): (43.5, 48.5),
        ("宁杞5号", "甲级", "中宁"): (34.0, 39.0),
        ("宁杞7号", "特级", "诺木洪"): (40.0, 46.0),
        ("宁杞1号", "甲级", "中宁"): (30.0, 34.5),
    }
    rows: list[MarketQuote] = []
    for (variety, grade, origin), (low, high) in specs.items():
        for days_ago in range(90):
            date = today - dt.timedelta(days=days_ago)
            base = low + (high - low) * (1 - days_ago / 120)  # 缓慢上行
            noise = random.uniform(-0.9, 0.9)
            rows.append(
                MarketQuote(
                    variety=variety,
                    grade=grade,
                    origin=origin,
                    spec_per_50g=280,
                    price=round(base + noise, 2),
                    volume=round(random.uniform(120, 860), 1),
                    stat_date=date,
                    quote_type="deal",
                    source="平台成交",
                )
            )
    session.add_all(rows)
    session.commit()
    print(f"  行情样本 {len(rows)} 条")


def seed_docs(session) -> None:
    from app.models.kb import KbDocument

    if session.query(KbDocument).count() > 0:
        print("  跳过知识库（已有数据）")
        return

    docs = [
        ("枸杞分级与术语标准（GB/T 18672 摘录）", "standard", "gbt-18672.md", DOC_GBT),
        ("平台商品审核规则", "rule", "audit-rules.md", DOC_RULES),
        ("枸杞储存常见问题", "faq", "storage-faq.md", DOC_STORAGE),
    ]
    for title, doc_type, filename, content in docs:
        data = content.encode("utf-8")
        doc = kb_service.create_document(
            session,
            filename=filename,
            data=data,
            content_type="text/markdown",
            title=title,
            doc_type=doc_type,
            chunk_strategy="auto",
        )
        session.commit()  # 每篇独立提交，失败不影响已入库文档
        print(f"  文档 {title}：策略 {doc.chunk_strategy}，切片 {doc.chunk_count}，状态 {doc.status}")
        assert doc.status == 2, f"入库失败：{doc.error_msg}"

def main() -> None:
    setup_logging("INFO")
    print("== 建表 ==")
    create_all()

    print("== 初始化数据 ==")
    session = SessionLocal()
    try:
        seed_users(session)
        seed_market(session)
        seed_docs(session)
    finally:
        session.close()
    print("完成")


if __name__ == "__main__":
    main()
