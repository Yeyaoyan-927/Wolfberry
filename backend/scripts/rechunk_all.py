"""知识库切分质量体检 + 批量重切。

背景：早期入库用的是"按条款逐条切"，条款式文档每条只有一句话，
切出来平均 30 字、最短 8 字——embedding 信息量不足，检索能命中但答不出内容。
本脚本做两件事：

    python scripts/rechunk_all.py             # 体检（只读，报告每篇切分质量）
    python scripts/rechunk_all.py --fix       # 对碎片化文档按新参数重切
    python scripts/rechunk_all.py --fix --all # 全部重切（含质量及格的）

判定碎片化：平均长度 < 80 字，或过短块（<60 字）占比 > 30%。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import SessionLocal  # noqa: E402
from app.models.kb import DOC_INDEXED, KbChunk, KbDocument  # noqa: E402
from app.rag.splitter import SHORT_THRESHOLD  # noqa: E402
from app.services import kb_service  # noqa: E402

AVG_MIN = 80          # 平均长度低于此值视为碎片化
SHORT_RATIO_MAX = 0.3  # 过短块占比上限


def inspect_doc(session, doc: KbDocument) -> dict:
    # FAQ 按「一问一答」切分，每片本身就该短，不参与长度体检
    if doc.chunk_strategy == "qa":
        lens = [
            c.char_count
            for c in session.scalars(select(KbChunk).where(KbChunk.doc_id == doc.id)).all()
        ]
        return {"count": len(lens), "avg": round(sum(lens) / len(lens), 1) if lens else 0,
                "min": min(lens) if lens else 0, "max": max(lens) if lens else 0,
                "short_ratio": 0.0, "fragmented": False}

    lens = [
        c.char_count
        for c in session.scalars(select(KbChunk).where(KbChunk.doc_id == doc.id)).all()
    ]
    n = len(lens)
    if n == 0:
        return {"count": 0, "avg": 0, "short_ratio": 1.0, "fragmented": True}
    avg = sum(lens) / n
    short_ratio = sum(1 for x in lens if x < SHORT_THRESHOLD) / n
    return {
        "count": n,
        "avg": round(avg, 1),
        "min": min(lens),
        "max": max(lens),
        "short_ratio": round(short_ratio, 3),
        "fragmented": avg < AVG_MIN or short_ratio > SHORT_RATIO_MAX,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="执行重切")
    parser.add_argument("--all", action="store_true", help="连同质量及格的文档一起重切")
    parser.add_argument("--size", type=int, default=400, help="目标块长")
    parser.add_argument("--overlap", type=int, default=80, help="块间重叠")
    parser.add_argument("--strategy", default="auto", help="切分策略（默认 auto 自动探测）")
    args = parser.parse_args()

    setup_logging("WARNING")
    session = SessionLocal()
    try:
        docs = session.scalars(
            select(KbDocument).where(KbDocument.status == DOC_INDEXED).order_by(KbDocument.id)
        ).all()
        print(f"体检 {len(docs)} 篇已入库文档（目标参数：策略 {args.strategy} / 块长 {args.size} / 重叠 {args.overlap}）")
        print("-" * 78)

        targets: list[KbDocument] = []
        for doc in docs:
            st = inspect_doc(session, doc)
            flag = "碎片化" if st["fragmented"] else "合格  "
            print(f"  [{flag}] #{doc.id:>2} {doc.title[:26]:28} "
                  f"{st['count']:>3} 片 · 平均 {st['avg']:>5} 字 · "
                  f"{st['min']}~{st['max']} · 过短 {st['short_ratio']:.0%}")
            if st["fragmented"] or args.all:
                targets.append(doc)

        if not args.fix:
            print(f"\n待重切 {len(targets)} 篇。加 --fix 执行（--all 可含合格文档）")
            return

        print(f"\n开始重切 {len(targets)} 篇…")
        for doc in targets:
            before = inspect_doc(session, doc)
            try:
                result = kb_service.rechunk(
                    session, doc,
                    strategy=args.strategy,
                    chunk_size=args.size,
                    chunk_overlap=args.overlap,
                )
                session.commit()
                after = inspect_doc(session, doc)
                print(f"  ✓ #{doc.id} {doc.title[:22]:24} "
                      f"{before['count']} 片/{before['avg']} 字 → "
                      f"{after['count']} 片/{after['avg']} 字（策略 {result['strategy']}）")
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                print(f"  ✗ #{doc.id} {doc.title[:22]} 重切失败：{exc}")

        print("\n重切后复核：")
        for doc in docs:
            st = inspect_doc(session, doc)
            flag = "碎片化" if st["fragmented"] else "合格  "
            print(f"  [{flag}] #{doc.id:>2} {doc.title[:26]:28} {st['count']:>3} 片 · 平均 {st['avg']} 字")
    finally:
        session.close()


if __name__ == "__main__":
    main()
