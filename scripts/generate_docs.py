#!/usr/bin/env python3
"""สร้าง docs/lineage.md และ docs/data-dictionary.md จาก artifacts ของ dbt

อ่าน dbt/target/manifest.json + catalog.json ซึ่ง `dbt docs generate` สร้างไว้
เอกสารสองไฟล์นี้จึงตรงกับโค้ดเสมอ ไม่ต้องแก้มือให้ลืม

ใช้:  make docs-gen      (จะรัน dbt docs generate ให้ก่อน)
"""

import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "dbt" / "target"
DOCS = ROOT / "docs"

LAYERS = [
    ("stg_hn__stories", "silver", "1 แถว = 1 story (snapshot ล่าสุด) → `story_id`"),
    ("fct_stories", "gold — fact", "1 แถว = 1 story → `story_id`"),
    ("dim_authors", "gold — dimension", "1 แถว = 1 author → `author`"),
    ("agg_daily_activity", "gold — aggregate", "1 แถว = 1 วัน → `activity_date`"),
]


def load():
    for name in ("manifest.json", "catalog.json"):
        if not (TARGET / name).exists():
            sys.exit(f"ไม่พบ {TARGET / name} — รัน `make dbt-docs` ก่อน")
    return (json.loads((TARGET / "manifest.json").read_text()),
            json.loads((TARGET / "catalog.json").read_text()))


def column_tests(man):
    """map (node_uid, column) -> [ชื่อ test]"""
    out = collections.defaultdict(list)
    for node in man["nodes"].values():
        if node["resource_type"] != "test":
            continue
        name = (node.get("test_metadata") or {}).get("name", node["name"])
        col = node.get("column_name")
        if not col:
            continue
        for parent in node["depends_on"]["nodes"]:
            out[(parent, col)].append(name)
    return out


def tests_per_model(man):
    """นับ test ทั้งหมด (generic + singular + unit) ต่อ model"""
    counts = collections.Counter()
    for uid, node in man["nodes"].items():
        if node["resource_type"] != "test":
            continue
        for parent in man["parent_map"].get(uid, []):
            if parent in man["nodes"] and man["nodes"][parent]["resource_type"] == "model":
                counts[parent] += 1
    for unit in man.get("unit_tests", {}).values():
        for parent in unit.get("depends_on", {}).get("nodes", []):
            counts[parent] += 1
    return counts


def write_lineage(man):
    models = {k: v for k, v in man["nodes"].items() if v["resource_type"] == "model"}
    by_name = {v["name"]: k for k, v in models.items()}
    counts = tests_per_model(man)
    ids, order = {}, []

    def nid(uid):
        if uid not in ids:
            ids[uid] = f"n{len(ids)}"
            order.append(uid)
        return ids[uid]

    lines = ["```mermaid", "graph LR",
             "    classDef src fill:#f6c177,stroke:#b4833a,color:#2b2118;",
             "    classDef stg fill:#9ccfd8,stroke:#3d7a84,color:#10262a;",
             "    classDef mart fill:#c4a7e7,stroke:#6d4fa3,color:#1e1428;"]

    for uid, src in man["sources"].items():
        lines.append(f'    {nid(uid)}["🗄️ {src["schema"]}.{src["name"]}'
                     f'<br/><small>bronze · MergeTree</small>"]:::src')

    for name, _, _ in LAYERS:
        uid = by_name[name]
        node = models[uid]
        layer = "silver" if node["schema"].endswith("staging") else "gold"
        cls = "stg" if layer == "silver" else "mart"
        lines.append(f'    {nid(uid)}["{name}<br/><small>{layer} · '
                     f'{node["config"]["materialized"]} · {counts.get(uid, 0)} tests</small>"]:::{cls}')

    edges = {(p, uid) for uid in models for p in man["parent_map"].get(uid, [])
             if p in models or p in man["sources"]}
    for a, b in sorted(edges, key=lambda e: (ids.get(e[0], ""), ids.get(e[1], ""))):
        lines.append(f"    {nid(a)} --> {nid(b)}")
    lines.append("```")

    total = sum(1 for n in man["nodes"].values() if n["resource_type"] == "test") \
        + len(man.get("unit_tests", {}))

    (DOCS / "lineage.md").write_text(f"""# Lineage — จาก Hacker News ถึง dashboard

> สร้างอัตโนมัติด้วย `make docs-gen` — อย่าแก้ไฟล์นี้ด้วยมือ

{chr(10).join(lines)}

## อ่านกราฟนี้ยังไง

| ชั้น | สี | ทำอะไร |
|---|---|---|
| **bronze** `hackernews.raw_stories` | ส้ม | landing zone — หน้าตาเหมือนที่ Algolia ส่งมา append อย่างเดียว เก็บทุก snapshot |
| **silver** `stg_hn__stories` | ฟ้า | ยุบเหลือ snapshot ล่าสุดต่อ story + ถอด HTML + คำนวณ field ช่วยวิเคราะห์ |
| **gold** marts | ม่วง | ตารางที่ธุรกิจใช้จริง จัดแบบ Kimball (fact + dimension) + ตาราง aggregate สำหรับ dashboard |

ทุก mart อ่านจาก `stg_hn__stories` ตัวเดียว ไม่มี mart ไหนแตะ `raw_stories` ตรงๆ
นั่นคือเหตุผลที่ dedup ทำที่เดียวแล้วทั้งระบบได้ประโยชน์

## ทำไม mart ไม่ `ref()` กันเอง

แต่ละ mart มี grain ของตัวเอง (1 story / 1 author / 1 วัน) ถ้าให้ `agg_daily_activity`
อ่านจาก `fct_stories` จะประหยัดได้นิดหน่อย แต่ผูกสองตารางเข้าด้วยกันโดยไม่จำเป็น —
แก้ `fct` ทีเดียว `agg` พังตาม ตอนนี้ทั้งคู่ขึ้นกับ staging เท่านั้น และมี singular test
`assert_daily_activity_reconciles_with_fct` คอยยืนยันว่าตัวเลขสองทางตรงกัน

## สถิติ ณ ตอน generate

- {len(models)} models · {len(man["sources"])} source · **{total} tests**
- ดูฉบับโต้ตอบ: `make dbt-docs` แล้วเปิด `dbt/target/index.html`
""")
    return len(models), total


def write_dictionary(man, cat):
    col_tests = column_tests(man)

    def table(uid, entry, store):
        types = {c["name"]: c["type"]
                 for c in ((store.get(uid) or {}).get("columns") or {}).values()}
        documented = entry.get("columns") or {}
        rows = ["| คอลัมน์ | ชนิด | คำอธิบาย | tests |", "|---|---|---|---|"]
        for col in (types or documented):
            desc = (documented.get(col) or {}).get("description", "").strip().replace("\n", " ")
            # description หลายอันมี "|" อยู่ (เช่น "ask_hn | show_hn | story")
            # ถ้าไม่ escape ตาราง markdown จะแตกเป็นคอลัมน์เกิน
            desc = desc.replace("|", "\\|")
            names = col_tests.get((uid, col), [])
            rows.append(f"| `{col}` | `{types.get(col, '—')}` | {desc or '—'} | "
                        f"{', '.join(f'`{t}`' for t in names) if names else '—'} |")
        return rows

    out = ["""# Data Dictionary

> สร้างอัตโนมัติด้วย `make docs-gen` — อย่าแก้ไฟล์นี้ด้วยมือ
> คำอธิบายคอลัมน์มาจาก `description:` ใน schema yml ของ dbt

| ชั้น | Database | ใครสร้าง |
|---|---|---|
| bronze (raw) | `hackernews` | Airflow task `load_clickhouse_raw` |
| silver (staging) | `hackernews_staging` | dbt |
| gold (marts) | `hackernews_marts` | dbt |
"""]

    uid, src = next(iter(man["sources"].items()))
    out += [f"\n## 🗄️ `{src['schema']}.{src['name']}` — bronze\n",
            (src.get("description") or "").strip() + "\n",
            "**Grain:** 1 แถว = 1 snapshot ของ 1 story → `(story_id, ingested_at)`  ",
            "**Engine:** `MergeTree` · `PARTITION BY ingest_date` · `ORDER BY (story_id, ingested_at)`\n"]
    out += table(uid, src, cat["sources"])

    by_name = {v["name"]: k for k, v in man["nodes"].items() if v["resource_type"] == "model"}
    for name, layer, grain in LAYERS:
        uid = by_name[name]
        node = man["nodes"][uid]
        out += [f"\n## `{node['schema']}.{name}` — {layer}\n",
                (node.get("description") or "").strip() + "\n",
                f"**Grain:** {grain}  ",
                f"**Materialized:** `{node['config']['materialized']}`\n"]
        out += table(uid, node, cat["nodes"])

    out.append((ROOT / "docs" / "_pii_section.md").read_text())
    (DOCS / "data-dictionary.md").write_text("\n".join(out))


def main():
    man, cat = load()
    models, tests = write_lineage(man)
    write_dictionary(man, cat)
    print(f"เขียนแล้ว: docs/lineage.md, docs/data-dictionary.md ({models} models, {tests} tests)")


if __name__ == "__main__":
    main()
