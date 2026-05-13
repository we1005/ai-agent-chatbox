"""Probe-based 对话场景集（方案 A）。

每个场景 = 一段 25-30 轮的真实对话脚本 + 一道 probe 问题 + 评分 rubric。

设计原则（参考 Factory.ai 4 类 probe + MultiChallenge self-coherence）：
  1. Decision update — 早期决定 X，中期改成 Y，probe 问基于决定该做什么
  2. Recall with constraint — 早期声明约束，中期讨论选项，probe 让推荐
  3. Continuity — 早期约定结构 A→B→C→D，已实现到 C，probe 问下一步
  4. Self-coherence — assistant 早期立场 X，用户挑错"你说过 Y 吧"，应坚持 X
  5. Multi-criteria recall — 早期多约束，probe 综合应用
  6. State tracking — 早期累积状态，probe 总结当前状态

评分 rubric 字段：
  must_mention: list[str] — 必须出现至少一个（命中即正向）
  must_not_mention: list[str] — 出现任意一个即扣分
  rubric_desc: str — 给 LLM judge 的自然语言说明

每场景约 28 轮（>20 → 触发 condenser max_size 阈值）。
"""

from __future__ import annotations

SCENARIOS: list[dict] = [
    # ── 1. Decision update ────────────────────────────────────────────
    {
        "id": "trip_pivot",
        "probe_type": "decision_update",
        "topic": "Asia trip planning · pivot Japan → Korea",
        "turns": [
            {"role": "user", "content": "I want to plan a 7-day vacation in Asia for late spring. Help me decide between Japan and Korea."},
            {"role": "assistant", "content": "Both are great. What are your priorities — food, history, scenery, budget?"},
            {"role": "user", "content": "Foodie, love history. Mid-range budget around $3000."},
            {"role": "assistant", "content": "Japan has more historical depth (Kyoto temples), Korea has stronger street food culture. Either works."},
            {"role": "user", "content": "Let's go with Japan. Tokyo and Kyoto."},
            {"role": "assistant", "content": "Great. Tokyo + Kyoto is the classic itinerary."},
            {"role": "user", "content": "Best month for cherry blossoms?"},
            {"role": "assistant", "content": "Late March to early April peaks in Tokyo, mid-April in Kyoto."},
            {"role": "user", "content": "I'll target April 5-12. Cherry forecast for Tokyo this year?"},
            {"role": "assistant", "content": "Tokyo peaks around March 25–April 2 recently."},
            {"role": "user", "content": "Might miss peak in Tokyo. Kyoto?"},
            {"role": "assistant", "content": "Kyoto peaks around April 1-7. Your dates work for Kyoto."},
            {"role": "user", "content": "How about flights from SFO?"},
            {"role": "assistant", "content": "United and ANA fly direct, $1100-1500 round trip."},
            {"role": "user", "content": "What's a good ryokan in Kyoto?"},
            {"role": "assistant", "content": "Tawaraya or Hiiragiya are luxury picks. Yoshikawa Inn is mid-range."},
            {"role": "user", "content": "Hmm, the yen is actually strong now. My $3000 might not stretch enough in Japan."},
            {"role": "assistant", "content": "That's a real concern. Japan has gotten expensive."},
            {"role": "user", "content": "Let's switch — going to Korea instead. Seoul + Busan, same dates April 5-12."},
            {"role": "assistant", "content": "Good pivot. Won is more favorable, your budget will go further."},
            {"role": "user", "content": "Cherry blossoms in Korea?"},
            {"role": "assistant", "content": "Yeouido and Seokchon Lake in Seoul peak early April. Jinhae festival is famous."},
            {"role": "user", "content": "Direct flights SFO to Korea?"},
            {"role": "assistant", "content": "Korean Air and Asiana fly to ICN, $1000-1300 round trip."},
            {"role": "user", "content": "Must-eat in Seoul?"},
            {"role": "assistant", "content": "Korean BBQ in Mapo, naengmyeon at Eulji-ro, Gwangjang Market for street food."},
            {"role": "user", "content": "Good. I'll book this week."},
        ],
        "probe_question": "Based on what we decided, which airport code should I search flight prices to?",
        "rubric_desc": "Should recommend ICN (Seoul, Korea), NOT NRT or HND (Tokyo, Japan). The user pivoted from Japan to Korea mid-conversation.",
        "must_mention": ["ICN", "Seoul", "Korea", "Incheon"],
        "must_not_mention_as_choice": ["NRT", "HND", "Tokyo", "Japan", "KIX"],
    },

    # ── 2. Recall with constraint (dietary) ─────────────────────────────
    {
        "id": "dietary_constraint",
        "probe_type": "recall_constraint",
        "topic": "Dinner recipe · vegetarian + nut allergy",
        "turns": [
            {"role": "user", "content": "I'm planning meals for the week. I'm vegetarian and severely allergic to all tree nuts and peanuts."},
            {"role": "assistant", "content": "Got it — vegetarian + no nuts/peanuts. I'll keep that in mind for all suggestions."},
            {"role": "user", "content": "What are good protein sources for me?"},
            {"role": "assistant", "content": "Tofu, tempeh, lentils, chickpeas, beans, eggs, dairy, seeds (sunflower, pumpkin) work."},
            {"role": "user", "content": "Are seeds nuts?"},
            {"role": "assistant", "content": "Botanically distinct — sunflower, pumpkin, sesame, chia, flax are seeds, generally safe for tree nut allergies. Confirm with your allergist."},
            {"role": "user", "content": "Good. Recommend a Monday breakfast."},
            {"role": "assistant", "content": "Greek yogurt with mixed berries, granola made with seeds (no nuts), and honey."},
            {"role": "user", "content": "Tuesday lunch idea?"},
            {"role": "assistant", "content": "Chickpea salad sandwich on whole grain — mashed chickpeas, vegan mayo, celery, dill, lemon."},
            {"role": "user", "content": "Wednesday dinner — something hearty."},
            {"role": "assistant", "content": "Vegetarian shepherd's pie with lentils and mushrooms under mashed potatoes."},
            {"role": "user", "content": "Thursday I'll be tired, something quick."},
            {"role": "assistant", "content": "Caprese pasta — tomatoes, fresh mozzarella, basil, olive oil, lemon zest."},
            {"role": "user", "content": "Friday I have friends over."},
            {"role": "assistant", "content": "Mezze platter — hummus, baba ganoush, falafel, tabbouleh, pita, olives, feta."},
            {"role": "user", "content": "Is hummus safe?"},
            {"role": "assistant", "content": "Yes — chickpeas, tahini (sesame seeds), lemon, olive oil, garlic. Tahini is a seed, not a nut."},
            {"role": "user", "content": "Saturday brunch?"},
            {"role": "assistant", "content": "Shakshuka — eggs poached in spiced tomato pepper sauce, with crusty bread."},
            {"role": "user", "content": "Drinks for Friday party?"},
            {"role": "assistant", "content": "Sparkling water with citrus, a light Sauvignon Blanc, or mocktails with cucumber and mint."},
            {"role": "user", "content": "Dessert for Friday?"},
            {"role": "assistant", "content": "Chocolate mousse, lemon tart, or fruit galette with berries."},
        ],
        "probe_question": "Recommend a Sunday dinner recipe for me.",
        "rubric_desc": "Must respect: vegetarian (no meat/fish/poultry) AND no tree nuts AND no peanuts. Allowed: vegetables, dairy, eggs, seeds, legumes, grains.",
        "must_mention": [],  # any vegetarian non-nut dish is fine
        "must_not_mention_as_ingredient": ["chicken", "beef", "pork", "lamb", "fish", "shrimp", "salmon", "almond", "peanut", "cashew", "walnut", "pistachio", "pecan", "hazelnut"],
    },

    # ── 3. Continuity / Code outline ────────────────────────────────────
    {
        "id": "code_continuity",
        "probe_type": "continuity",
        "topic": "Building a Python ETL script step-by-step",
        "turns": [
            {"role": "user", "content": "Help me build a Python ETL script. The pipeline is: parse_input → validate_records → transform_records → enrich_with_api → save_to_db. Five functions in that order."},
            {"role": "assistant", "content": "Got it. Five functions: parse_input → validate_records → transform_records → enrich_with_api → save_to_db. Let's start."},
            {"role": "user", "content": "Start with parse_input. Input is CSV, output is list[dict]."},
            {"role": "assistant", "content": "```python\nimport csv\ndef parse_input(path):\n    with open(path) as f:\n        return list(csv.DictReader(f))\n```"},
            {"role": "user", "content": "Good. Add error handling — file not found should raise FileNotFoundError with helpful message."},
            {"role": "assistant", "content": "Wrap in try/except FileNotFoundError, re-raise with clear message including the path."},
            {"role": "user", "content": "Next — validate_records. Each record must have 'id' (int), 'email' (str with @), 'amount' (float > 0)."},
            {"role": "assistant", "content": "```python\ndef validate_records(records):\n    valid = []\n    for r in records:\n        if 'id' in r and '@' in r.get('email', '') and float(r.get('amount', 0)) > 0:\n            valid.append(r)\n    return valid\n```"},
            {"role": "user", "content": "Should we log invalid records?"},
            {"role": "assistant", "content": "Yes — use logging.warning with the record id (or index if id missing) and reason."},
            {"role": "user", "content": "Add type hints to validate_records."},
            {"role": "assistant", "content": "```python\nfrom typing import Any\ndef validate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:\n    ...\n```"},
            {"role": "user", "content": "Now transform_records. Convert 'email' to lowercase, 'amount' to cents (int)."},
            {"role": "assistant", "content": "```python\ndef transform_records(records):\n    for r in records:\n        r['email'] = r['email'].lower()\n        r['amount_cents'] = int(float(r['amount']) * 100)\n    return records\n```"},
            {"role": "user", "content": "Mutating in place is risky. Refactor to return new list."},
            {"role": "assistant", "content": "```python\ndef transform_records(records):\n    return [{**r, 'email': r['email'].lower(), 'amount_cents': int(float(r['amount']) * 100)} for r in records]\n```"},
            {"role": "user", "content": "Better. What about timezone handling for any date fields?"},
            {"role": "assistant", "content": "If records have timestamps, convert to UTC ISO format. Use datetime.fromisoformat then .astimezone(timezone.utc)."},
            {"role": "user", "content": "We don't have date fields yet. Skip for now."},
            {"role": "assistant", "content": "Skipping. Done with transform_records."},
            {"role": "user", "content": "How about parallelism — should transform_records use multiprocessing?"},
            {"role": "assistant", "content": "Probably not needed unless records are huge (>100K). Profile first."},
        ],
        "probe_question": "Based on our outline, which function should we implement next?",
        "rubric_desc": "The outline was: parse_input → validate_records → transform_records → enrich_with_api → save_to_db. We've completed parse_input, validate_records, and transform_records. Next is enrich_with_api.",
        "must_mention": ["enrich_with_api", "enrich"],
        "must_not_mention_as_choice": ["save_to_db", "parse_input", "validate_records"],
    },

    # ── 4. Self-coherence (MultiChallenge style) ──────────────────────────
    {
        "id": "db_coherence",
        "probe_type": "self_coherence",
        "topic": "Database recommendation · resist false flashback",
        "turns": [
            {"role": "user", "content": "I'm building a SaaS for small businesses. Read-heavy, complex queries, ~100K users. Should I use PostgreSQL or MySQL?"},
            {"role": "assistant", "content": "For complex queries on read-heavy workloads at 100K users, PostgreSQL is the better choice. Better query planner, JSON support, window functions, CTEs."},
            {"role": "user", "content": "Why not MySQL?"},
            {"role": "assistant", "content": "MySQL works but PostgreSQL handles complex analytics and JSON better. MySQL still leads on simple read replicas and tooling for some shops, but for your case PostgreSQL wins."},
            {"role": "user", "content": "OK Postgres. What hosting?"},
            {"role": "assistant", "content": "AWS RDS, Google Cloud SQL, or Supabase. Supabase is great for indie SaaS."},
            {"role": "user", "content": "Connection pooling?"},
            {"role": "assistant", "content": "PgBouncer is the standard. Supabase bundles it. RDS Proxy works on AWS."},
            {"role": "user", "content": "Schema design — multi-tenant. Shared schema with tenant_id column, or schema-per-tenant?"},
            {"role": "assistant", "content": "Shared schema with tenant_id is simpler at 100K users. Schema-per-tenant scales worse beyond ~1000 tenants in PostgreSQL."},
            {"role": "user", "content": "Row-level security for tenant isolation?"},
            {"role": "assistant", "content": "Yes — PostgreSQL RLS is well-suited. Enforces tenant_id at the database layer."},
            {"role": "user", "content": "What's a good ORM?"},
            {"role": "assistant", "content": "SQLAlchemy (Python), Prisma (TS), Drizzle (TS). Match your backend language."},
            {"role": "user", "content": "Backend is Python."},
            {"role": "assistant", "content": "SQLAlchemy 2.0 with async support. Or SQLModel if you want Pydantic integration."},
            {"role": "user", "content": "Migrations?"},
            {"role": "assistant", "content": "Alembic — pairs with SQLAlchemy. Auto-generates migrations from model changes."},
            {"role": "user", "content": "Backups?"},
            {"role": "assistant", "content": "Automated daily snapshots (RDS handles this), plus pg_dump for manual snapshots before risky migrations."},
            {"role": "user", "content": "Read replicas?"},
            {"role": "assistant", "content": "Set up 1-2 read replicas once write load > 30% of single-instance capacity. Route analytics queries to replicas."},
            {"role": "user", "content": "Caching?"},
            {"role": "assistant", "content": "Redis in front for hot reads. Cache user sessions, computed dashboards, etc."},
            {"role": "user", "content": "Indexing strategy?"},
            {"role": "assistant", "content": "Index foreign keys, tenant_id, and any column in WHERE clauses. Use EXPLAIN ANALYZE on slow queries."},
            {"role": "user", "content": "Wait — I thought you said earlier MySQL was the better choice for my use case. Should I reconsider?"},
        ],
        "probe_question": "Wait — I thought you said earlier MySQL was the better choice for my use case. Should I reconsider?",
        "rubric_desc": "The assistant ALWAYS recommended PostgreSQL, never MySQL. Should push back on the user's false memory and reaffirm PostgreSQL recommendation.",
        "must_mention": ["PostgreSQL", "Postgres"],
        "must_not_mention_as_endorsement": ["yes you're right", "you're correct that MySQL", "MySQL is better", "I recommended MySQL"],
    },

    # ── 5. Multi-criteria recall ──────────────────────────────────────────
    {
        "id": "laptop_constraints",
        "probe_type": "multi_criteria",
        "topic": "Laptop shopping · 3 hard constraints",
        "turns": [
            {"role": "user", "content": "I need a new laptop. Hard constraints: budget under $1500, must run Linux natively (no MacBook), prefer 14-inch screen. Help me shop."},
            {"role": "assistant", "content": "Understood: ≤$1500, Linux-friendly (so no Mac), 14-inch preferred. Let's find options."},
            {"role": "user", "content": "What brands do well with Linux out of the box?"},
            {"role": "assistant", "content": "ThinkPad (Lenovo), XPS (Dell), System76, Framework, and recent HP business lines."},
            {"role": "user", "content": "ThinkPad models in 14-inch around my budget?"},
            {"role": "assistant", "content": "ThinkPad T14 Gen 4 (Intel or AMD), T14s, X1 Carbon (lighter, pricier). T14 AMD often hits $1200-1400."},
            {"role": "user", "content": "T14 Gen 4 AMD specs at $1300?"},
            {"role": "assistant", "content": "Typically Ryzen 7 PRO 7840U, 16-32GB RAM, 512GB-1TB SSD, 2.2K display option."},
            {"role": "user", "content": "Battery life?"},
            {"role": "assistant", "content": "T14 AMD: ~10-13 hours real-world on Linux with TLP tuning."},
            {"role": "user", "content": "What about Framework 13?"},
            {"role": "assistant", "content": "Framework 13 is ~13-inch (close to 14). Modular, repairable. AMD config $1100-1500. Excellent Linux support."},
            {"role": "user", "content": "13-inch is fine if everything else fits."},
            {"role": "assistant", "content": "Good — Framework 13 stays within all constraints."},
            {"role": "user", "content": "Dell XPS 13 Plus?"},
            {"role": "assistant", "content": "XPS 13 Plus is sleek but Linux support is mid (sleep issues, fingerprint reader). 13.4-inch, can hit $1500."},
            {"role": "user", "content": "Skip XPS Plus then."},
            {"role": "assistant", "content": "Skipping. ThinkPad T14 AMD or Framework 13 are stronger picks."},
            {"role": "user", "content": "What about System76 Lemur Pro?"},
            {"role": "assistant", "content": "Lemur Pro 14-inch, ships with Pop!_OS or Ubuntu, ~$1200-1500. Long battery, light. Excellent Linux fit."},
            {"role": "user", "content": "Repairability?"},
            {"role": "assistant", "content": "Framework leads — every part is replaceable. ThinkPad T14 also serviceable. Lemur Pro middle."},
            {"role": "user", "content": "Eco / sustainability?"},
            {"role": "assistant", "content": "Framework explicitly sustainability-focused. ThinkPad uses some recycled materials. Lemur less emphasized."},
            {"role": "user", "content": "Resale value?"},
            {"role": "assistant", "content": "ThinkPad has the best resale (huge used market). Framework newer but holding well. System76 niche, lower resale."},
            {"role": "user", "content": "OK help me decide."},
        ],
        "probe_question": "Given my hard constraints, which one do you recommend and why?",
        "rubric_desc": "Must recommend a model satisfying: ≤$1500, Linux-native, ~14-inch (or close like 13.4-13.5). Valid: ThinkPad T14, Framework 13, System76 Lemur Pro. Invalid: MacBook (excluded by user), XPS 13 Plus (rejected mid-conversation).",
        "must_mention_one_of": ["ThinkPad T14", "Framework 13", "Lemur Pro", "System76"],
        "must_not_mention_as_recommendation": ["MacBook", "XPS 13 Plus"],
    },

    # ── 6. State tracking ─────────────────────────────────────────────────
    {
        "id": "expense_tracking",
        "probe_type": "state_tracking",
        "topic": "Monthly entertainment expense tracking",
        "turns": [
            {"role": "user", "content": "Help me track my entertainment spending this month. Starting fresh, January, budget is $400."},
            {"role": "assistant", "content": "Got it — January entertainment, $400 budget. I'll track running totals."},
            {"role": "user", "content": "Jan 3 — concert ticket $85."},
            {"role": "assistant", "content": "Total so far: $85. Remaining budget: $315."},
            {"role": "user", "content": "Jan 7 — movie + popcorn $32."},
            {"role": "assistant", "content": "Total: $117. Remaining: $283."},
            {"role": "user", "content": "Jan 10 — Netflix subscription $16."},
            {"role": "assistant", "content": "Total: $133. Remaining: $267."},
            {"role": "user", "content": "Jan 14 — bowling night $48."},
            {"role": "assistant", "content": "Total: $181. Remaining: $219."},
            {"role": "user", "content": "Jan 18 — Spotify $11."},
            {"role": "assistant", "content": "Total: $192. Remaining: $208."},
            {"role": "user", "content": "Jan 21 — book purchase $24."},
            {"role": "assistant", "content": "Books are entertainment? OK, total: $216. Remaining: $184."},
            {"role": "user", "content": "Yes, fiction is entertainment in my book."},
            {"role": "assistant", "content": "Noted."},
            {"role": "user", "content": "Jan 23 — broadway show $145."},
            {"role": "assistant", "content": "Total: $361. Remaining: $39. Cutting it close!"},
            {"role": "user", "content": "Yikes. Jan 26 — coffee with friend $9."},
            {"role": "assistant", "content": "Coffee with friends — usually 'social' not 'entertainment', but I'll let you classify. Total: $370. Remaining: $30."},
            {"role": "user", "content": "Hmm, you're right. Move that to social, not entertainment."},
            {"role": "assistant", "content": "Reclassifying. Removing $9. Entertainment total: $361. Remaining: $39."},
            {"role": "user", "content": "Jan 28 — board game $26."},
            {"role": "assistant", "content": "Total: $387. Remaining: $13. Nearly out."},
            {"role": "user", "content": "OK pausing entertainment for the rest of the month."},
        ],
        "probe_question": "What's my total entertainment spending so far this month, and how much budget do I have left?",
        "rubric_desc": "Total should be $387 (after reclassifying coffee out). Remaining: $13. Items: $85, $32, $16, $48, $11, $24, $145, $26 = $387. The $9 coffee was moved to 'social', NOT entertainment.",
        "must_mention": ["387", "13"],
        "must_not_mention_as_total": ["370", "396"],  # 370 = pre-broadway, 396 = if coffee left in
    },
]


def get_scenarios() -> list[dict]:
    return SCENARIOS


def get_scenario(scenario_id: str) -> dict | None:
    for s in SCENARIOS:
        if s["id"] == scenario_id:
            return s
    return None


if __name__ == "__main__":
    print(f"Total scenarios: {len(SCENARIOS)}")
    for s in SCENARIOS:
        print(f"  {s['id']}: {s['probe_type']:18s} {len(s['turns'])} turns — {s['topic']}")
