#!/usr/bin/env python3
"""Generate a deterministic, relational mock dataset for creator selection.

The production-facing tables contain observations and model features, not final
fraud/compliance answers. Hidden scenario labels live under data/evaluation and
must only be used for offline evaluation.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DEFAULT_SEED = 20260831
DEFAULT_AS_OF = date(2026, 8, 31)

PLATFORMS = ["抖音", "小红书", "B站", "微博"]
CATEGORIES = ["美妆个护", "时尚穿搭", "科技数码", "母婴育儿", "食品饮料", "健身运动", "家居生活", "旅行摄影"]
STYLES = ["知性温柔", "幽默轻松", "硬核测评", "精致高端", "亲和生活流", "视觉艺术", "专业科普"]
TOPICS = {
    "美妆个护": ["成分", "敏感肌", "通勤妆", "防晒", "香氛", "护肤实测"],
    "时尚穿搭": ["通勤", "轻奢", "国潮", "配色", "小个子", "面料"],
    "科技数码": ["参数", "续航", "影像", "办公效率", "游戏", "智能家居"],
    "母婴育儿": ["亲子", "辅食", "早教", "安全", "成长", "家庭出行"],
    "食品饮料": ["低糖", "配料表", "早餐", "咖啡", "探店", "便捷料理"],
    "健身运动": ["跑步", "力量训练", "瑜伽", "户外", "恢复", "运动装备"],
    "家居生活": ["收纳", "清洁", "家电", "软装", "租房改造", "睡眠"],
    "旅行摄影": ["城市漫游", "攻略", "酒店", "构图", "人文", "户外路线"],
}
FORMATS = {
    "抖音": ["短视频", "直播"],
    "小红书": ["图文", "短视频"],
    "B站": ["中长视频", "动态"],
    "微博": ["图文", "短视频"],
}
PLATFORM_ER = {"抖音": 0.040, "小红书": 0.060, "B站": 0.050, "微博": 0.025}
PLATFORM_VIEW_RATIO = {"抖音": 0.55, "小红书": 0.30, "B站": 0.38, "微博": 0.24}
TIER_RANGES = {
    "nano": (2_000, 10_000),
    "micro": (10_000, 100_000),
    "mid": (100_000, 500_000),
    "macro": (500_000, 2_000_000),
    "mega": (2_000_000, 8_000_000),
}
TIER_WEIGHTS = [0.28, 0.36, 0.23, 0.10, 0.03]

SURNAMES = ["林", "苏", "顾", "沈", "周", "陆", "唐", "夏", "宋", "许", "叶", "程", "江", "乔", "韩", "温"]
NICK_WORDS = ["小岛", "拾光", "阿白", "圆子", "研究所", "生活志", "实验室", "慢慢", "观察员", "日记", "清单", "指南"]
REGIONS = ["北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "重庆", "苏州", "长沙"]
INTERESTS = ["品质生活", "性价比", "健康", "科技尝鲜", "亲子家庭", "户外运动", "审美设计", "职场成长", "旅行", "美食"]

BRANDS = {
    "美妆个护": ["澄光护肤", "微澜美研", "森屿香氛", "初禾个护"],
    "时尚穿搭": ["织见", "青岚服饰", "序章箱包", "微光珠宝"],
    "科技数码": ["星云手机", "云帆电脑", "元点耳机", "北辰智家"],
    "母婴育儿": ["芽芽成长", "小树营养", "棉云童装", "安心出行"],
    "食品饮料": ["谷屿食品", "清醒咖啡", "轻田饮品", "一日食光"],
    "健身运动": ["跃野运动", "循迹跑鞋", "原力健身", "山海户外"],
    "家居生活": ["留白家居", "净界清洁", "眠屿寝具", "方寸收纳"],
    "旅行摄影": ["远方旅业", "见山酒店", "光屿影像", "步履户外"],
}

RISKY_PHRASES = {
    "美妆个护": ["七天焕白", "全网第一", "彻底修复"],
    "母婴育儿": ["绝对安全", "百分百提升", "全网第一"],
    "食品饮料": ["零负担", "吃了就瘦", "全网第一"],
    "科技数码": ["性能最强", "永不卡顿", "全网第一"],
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round_dict(values: dict[str, float], digits: int = 4) -> dict[str, float]:
    total = sum(values.values()) or 1.0
    rounded = {key: round(value / total, digits) for key, value in values.items()}
    drift = round(1.0 - sum(rounded.values()), digits)
    last = next(reversed(rounded))
    rounded[last] = round(rounded[last] + drift, digits)
    return rounded


def dirichlet_like(rng: random.Random, keys: list[str], emphasis: int | None = None) -> dict[str, float]:
    values = {}
    for idx, key in enumerate(keys):
        shape = 4.0 if emphasis == idx else 1.4
        values[key] = rng.gammavariate(shape, 1.0)
    return round_dict(values)


def log_uniform_int(rng: random.Random, low: int, high: int) -> int:
    return int(math.exp(rng.uniform(math.log(low), math.log(high))))


def iso(day: date) -> str:
    return day.isoformat()


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def make_name(rng: random.Random, idx: int) -> str:
    return f"{rng.choice(SURNAMES)}{rng.choice(NICK_WORDS)}_{idx:03d}"


def follower_tier(rng: random.Random) -> tuple[str, int]:
    tier = rng.choices(list(TIER_RANGES), weights=TIER_WEIGHTS, k=1)[0]
    low, high = TIER_RANGES[tier]
    return tier, log_uniform_int(rng, low, high)


def price_for(account: dict[str, Any], content_format: str, rng: random.Random) -> int:
    followers = account["follower_count_current"]
    platform_factor = {"抖音": 1.15, "小红书": 1.05, "B站": 1.30, "微博": 0.85}[account["platform"]]
    format_factor = {"图文": 0.75, "短视频": 1.0, "中长视频": 1.45, "动态": 0.55, "直播": 1.75}[content_format]
    quality_factor = 0.75 + account["_quality"] * 0.7
    raw = 420 * ((followers / 1_000) ** 0.72) * platform_factor * format_factor * quality_factor
    return max(500, int(round(raw * rng.uniform(0.88, 1.12) / 100) * 100))


def generate_entities(rng: random.Random, creator_count: int, as_of: date) -> tuple[list[dict], list[dict]]:
    creators: list[dict] = []
    accounts: list[dict] = []
    used_names: set[str] = set()
    for idx in range(1, creator_count + 1):
        name = make_name(rng, idx)
        while name in used_names:
            name = make_name(rng, idx)
        used_names.add(name)
        primary_category = rng.choice(CATEGORIES)
        secondary = rng.choice([c for c in CATEGORIES if c != primary_category]) if rng.random() < 0.32 else None
        category_tags = [primary_category] + ([secondary] if secondary else [])
        style_tags = rng.sample(STYLES, k=rng.choice([1, 1, 2]))
        creator_id = f"cr_{idx:04d}"
        creators.append({
            "creator_id": creator_id,
            "display_name": name,
            "is_fictional": True,
            "home_region": rng.choice(REGIONS),
            "languages": ["普通话"] + (["英语"] if rng.random() < 0.18 else []),
            "category_tags": category_tags,
            "style_tags": style_tags,
            "public_persona_summary": f"专注{primary_category}，内容风格偏{style_tags[0]}。",
            "created_at": iso(as_of - timedelta(days=rng.randint(700, 2600))),
        })

        platform_count = 2 if rng.random() < 0.24 else 1
        for platform in rng.sample(PLATFORMS, k=platform_count):
            tier, followers = follower_tier(rng)
            account_idx = len(accounts) + 1
            quality = rng.betavariate(5, 2.2)
            authenticity = rng.betavariate(9, 1.8)
            professionalism = rng.betavariate(6, 2)
            accounts.append({
                "account_id": f"acc_{account_idx:05d}",
                "creator_id": creator_id,
                "platform": platform,
                "handle": f"{name}_{platform}",
                "profile_url": f"https://example.invalid/{platform}/{account_idx:05d}",
                "verification_status": rng.choices(["verified", "unverified"], [0.38, 0.62], k=1)[0],
                "creator_tier": tier,
                "follower_count_current": followers,
                "primary_category": primary_category,
                "category_tags": category_tags,
                "style_tags": style_tags,
                "region": rng.choice(REGIONS),
                "account_status": "active",
                "data_source": "synthetic_platform_api",
                "collected_at": iso(as_of),
                "data_confidence": round(rng.uniform(0.86, 0.99), 3),
                "_quality": quality,
                "_authenticity": authenticity,
                "_professionalism": professionalism,
                "_scenario": [],
            })
    return creators, accounts


def assign_scenarios(rng: random.Random, accounts: list[dict]) -> None:
    scenario_rates = {
        "fake_growth_burst": 0.055,
        "reputation_crisis": 0.040,
        "missing_ad_disclosure": 0.070,
        "risky_claim": 0.045,
        "delivery_unreliable": 0.055,
    }
    for index, account in enumerate(accounts):
        profile_bucket = index % 20
        account["_history_profile"] = (
            "HISTORY_SUFFICIENT"
            if profile_bucket < 15
            else "HISTORY_LIMITED"
            if profile_bucket < 19
            else "COLD_START"
        )
        for scenario, rate in scenario_rates.items():
            if rng.random() < rate:
                account["_scenario"].append(scenario)
        if "fake_growth_burst" in account["_scenario"]:
            account["_authenticity"] = rng.uniform(0.28, 0.58)
        if "delivery_unreliable" in account["_scenario"]:
            account["_professionalism"] = rng.uniform(0.25, 0.55)


def generate_audience_snapshots(rng: random.Random, accounts: list[dict], as_of: date) -> list[dict]:
    rows = []
    for account in accounts:
        gender_base = dirichlet_like(rng, ["female", "male", "unknown"], emphasis=rng.choice([0, 0, 1]))
        age_base = dirichlet_like(rng, ["under_18", "18_24", "25_34", "35_44", "45_plus"], emphasis=rng.choice([1, 2, 2, 3]))
        region_emphasis = REGIONS.index(account["region"])
        region_base = dirichlet_like(rng, REGIONS, emphasis=region_emphasis)
        interests = rng.sample(INTERESTS, k=4)
        for offset in [120, 60, 0]:
            authenticity = account["_authenticity"]
            sample_size = min(50_000, max(500, int(account["follower_count_current"] * rng.uniform(0.08, 0.24))))
            rows.append({
                "account_id": account["account_id"],
                "snapshot_date": iso(as_of - timedelta(days=offset)),
                "audience_gender_distribution": gender_base,
                "audience_age_distribution": age_base,
                "top_regions": dict(sorted(region_base.items(), key=lambda item: item[1], reverse=True)[:5]),
                "audience_interest_tags": interests,
                "active_follower_ratio": round(clamp(authenticity * rng.uniform(0.72, 0.98), 0.15, 0.95), 4),
                "suspicious_account_ratio_observed": round(clamp((1 - authenticity) * rng.uniform(0.55, 0.95), 0.01, 0.65), 4),
                "sample_size": sample_size,
                "measurement_method": "synthetic_audience_panel_v1",
                "confidence": round(clamp(0.72 + math.log10(sample_size) / 20, 0.75, 0.98), 3),
            })
    return rows


def generate_metric_snapshots(rng: random.Random, accounts: list[dict], as_of: date) -> list[dict]:
    rows = []
    for account in accounts:
        current = account["follower_count_current"]
        weekly_growth = rng.uniform(0.001, 0.018) * (0.7 + account["_quality"] * 0.6)
        counts = []
        value = current / ((1 + weekly_growth) ** 25)
        burst_week = rng.randint(17, 22) if "fake_growth_burst" in account["_scenario"] else None
        for week in range(26):
            if week == burst_week:
                value *= rng.uniform(1.20, 1.55)
            else:
                value *= 1 + weekly_growth + rng.uniform(-0.0025, 0.0025)
            counts.append(max(1_000, int(value)))
        scale = current / counts[-1]
        counts = [int(v * scale) for v in counts]
        counts[-1] = current

        for week, followers in enumerate(counts):
            day = as_of - timedelta(days=(25 - week) * 7)
            base_er = PLATFORM_ER[account["platform"]] * (0.65 + account["_quality"] * 0.75)
            if account["creator_tier"] in {"macro", "mega"}:
                base_er *= 0.74
            rows.append({
                "account_id": account["account_id"],
                "snapshot_date": iso(day),
                "follower_count": followers,
                "posts_last_7d": rng.randint(1, 6),
                "median_views_last_30d": max(100, int(followers * PLATFORM_VIEW_RATIO[account["platform"]] * rng.uniform(0.65, 1.35))),
                "engagement_rate_by_followers_30d": round(clamp(base_er * rng.uniform(0.78, 1.22), 0.003, 0.20), 5),
                "view_cv_30d": round(rng.uniform(0.18, 0.72) * (1.25 if "delivery_unreliable" in account["_scenario"] else 1), 4),
                "repetitive_comment_ratio_observed": round(
                    rng.uniform(0.28, 0.58) if "fake_growth_burst" in account["_scenario"] and week >= (burst_week or 99)
                    else rng.uniform(0.01, 0.13), 4
                ),
                "data_source": "synthetic_platform_api",
            })
    return rows


def content_text(category: str, style: str, topic: str, sponsored: bool, rng: random.Random) -> tuple[str, str]:
    openers = ["实测记录", "本周清单", "真实体验", "新手指南", "使用一周后", "今天聊聊"]
    endings = ["优缺点都说清楚", "适合自己的才重要", "数据和体验一起看", "欢迎理性讨论", "先收藏再慢慢看"]
    title = f"{rng.choice(openers)}｜{topic}{rng.choice(['怎么选', '避坑指南', '体验报告', '入门建议'])}"
    caption = f"以{style}的方式分享{category}中的{topic}，{rng.choice(endings)}。"
    if sponsored:
        caption += " 本内容含品牌合作。"
    return title, caption


def generate_contents(rng: random.Random, accounts: list[dict], as_of: date) -> tuple[list[dict], list[dict]]:
    contents: list[dict] = []
    risk_evidence: list[dict] = []
    for account in accounts:
        count = rng.randint(26, 44)
        category = account["primary_category"]
        style = account["style_tags"][0]
        crisis_cutoff = as_of - timedelta(days=24)
        for idx in range(count):
            published = as_of - timedelta(days=rng.randint(0, 179))
            sponsored = rng.random() < 0.22
            topic = rng.choice(TOPICS[category])
            title, caption = content_text(category, style, topic, sponsored, rng)
            ad_disclosure = sponsored
            risky_phrase = None
            if sponsored and "missing_ad_disclosure" in account["_scenario"] and rng.random() < 0.55:
                ad_disclosure = False
                caption = caption.replace(" 本内容含品牌合作。", "")
            if "risky_claim" in account["_scenario"] and category in RISKY_PHRASES and rng.random() < 0.16:
                risky_phrase = rng.choice(RISKY_PHRASES[category])
                caption += f" {risky_phrase}，欢迎体验。"

            followers = account["follower_count_current"]
            view_ratio = PLATFORM_VIEW_RATIO[account["platform"]] * rng.lognormvariate(-0.05, 0.48)
            views = max(80, int(followers * view_ratio))
            er = PLATFORM_ER[account["platform"]] * (0.62 + account["_quality"] * 0.8)
            engagements = max(4, int(views * er * rng.uniform(0.72, 1.30)))
            likes = int(engagements * rng.uniform(0.68, 0.84))
            comments = int(engagements * rng.uniform(0.06, 0.14))
            shares = int(engagements * rng.uniform(0.03, 0.09))
            saves = max(0, engagements - likes - comments - shares)
            negative = rng.betavariate(1.5, 10)
            if "reputation_crisis" in account["_scenario"] and published >= crisis_cutoff:
                negative = rng.uniform(0.45, 0.82)
            sentiment_score = clamp(1 - 2 * negative + rng.uniform(-0.08, 0.08), -1, 1)
            repetitive = "fake_growth_burst" in account["_scenario"] and published >= as_of - timedelta(days=55)
            comments_sample = ["支持一下", "看起来不错", "已收藏", "想看更多实测"]
            if repetitive:
                comments_sample = ["太棒了", "太棒了", "支持", "支持"]
            elif negative > 0.45:
                comments_sample = ["信息没有说清楚", "广告感太强", "和以前内容差别很大", "希望回应质疑"]

            content_id = f"ct_{len(contents) + 1:07d}"
            row = {
                "content_id": content_id,
                "account_id": account["account_id"],
                "published_at": iso(published),
                "content_format": rng.choice(FORMATS[account["platform"]]),
                "title": title,
                "caption": caption,
                "transcript": caption if account["platform"] in {"抖音", "B站"} else None,
                "ocr_text": risky_phrase,
                "topic_tags": [topic, category],
                "style_tags": [style],
                "mentioned_brands": [],
                "is_sponsored": sponsored,
                "ad_disclosure_present": ad_disclosure,
                "metrics": {"views": views, "impressions": int(views * rng.uniform(1.02, 1.30)), "likes": likes, "comments": comments, "shares": shares, "saves": saves},
                "comment_sample": comments_sample,
                "comment_sentiment": {
                    "score": round(sentiment_score, 4),
                    "negative_ratio": round(negative, 4),
                    "sample_size": rng.randint(40, min(1500, max(41, comments * 3 + 40))),
                    "model_version": "synthetic_sentiment_v1",
                    "confidence": round(rng.uniform(0.78, 0.96), 3),
                },
                "metric_collected_at": iso(as_of),
            }
            contents.append(row)
            if sponsored and not ad_disclosure:
                risk_evidence.append({"account_id": account["account_id"], "content_id": content_id, "scenario": "missing_ad_disclosure", "evidence": "合作内容未观察到广告标识"})
            if risky_phrase:
                risk_evidence.append({"account_id": account["account_id"], "content_id": content_id, "scenario": "risky_claim", "evidence": risky_phrase})
    return contents, risk_evidence


def generate_rate_cards(rng: random.Random, accounts: list[dict], as_of: date) -> list[dict]:
    rows = []
    for account in accounts:
        for content_format in FORMATS[account["platform"]]:
            base = price_for(account, content_format, rng)
            rows.append({
                "rate_card_id": f"rate_{len(rows) + 1:06d}",
                "account_id": account["account_id"],
                "content_format": content_format,
                "base_price_cny": base,
                "package_price_cny": int(base * rng.uniform(1.75, 2.55) // 100 * 100),
                "package_description": f"2条{content_format}+基础数据回传",
                "agency_fee_rate": round(rng.choice([0.0, 0.05, 0.10, 0.15]), 2),
                "negotiable": rng.random() < 0.62,
                "usage_rights_days_included": rng.choice([0, 30, 60, 90]),
                "exclusivity_days_included": rng.choice([0, 7, 14, 30]),
                "valid_from": iso(as_of - timedelta(days=30)),
                "valid_to": iso(as_of + timedelta(days=90)),
            })
    return rows


def generate_collaborations(rng: random.Random, accounts: list[dict], as_of: date, target_count: int) -> list[dict]:
    rows = []
    history_sufficient_accounts = [
        account for account in accounts if account["_history_profile"] == "HISTORY_SUFFICIENT"
    ]
    for _ in range(target_count):
        account = rng.choice(history_sufficient_accounts)
        category = rng.choice(account["category_tags"] if rng.random() < 0.68 else CATEGORIES)
        brand = rng.choice(BRANDS[category])
        end = as_of - timedelta(days=rng.randint(10, 720))
        start = end - timedelta(days=rng.randint(7, 50))
        content_format = rng.choice(FORMATS[account["platform"]])
        amount = price_for(account, content_format, rng)
        quality = account["_quality"]
        unreliable = "delivery_unreliable" in account["_scenario"]
        on_time = rng.random() < (0.66 if unreliable else 0.93)
        views = max(100, int(account["follower_count_current"] * PLATFORM_VIEW_RATIO[account["platform"]] * rng.uniform(0.55, 1.55)))
        engagements = max(5, int(views * PLATFORM_ER[account["platform"]] * (0.55 + quality) * rng.uniform(0.7, 1.3)))
        clicks = int(views * rng.uniform(0.004, 0.035))
        conversions = int(clicks * rng.uniform(0.012, 0.11))
        revenue = round(conversions * rng.uniform(80, 620), 2)
        rows.append({
            "collaboration_id": f"col_{len(rows) + 1:06d}",
            "account_id": account["account_id"],
            "brand_name": brand,
            "brand_category": category,
            "started_at": iso(start),
            "ended_at": iso(end),
            "content_format": content_format,
            "contract_amount_cny": amount,
            "status": "completed",
            "delivered_on_time": on_time,
            "revision_count": rng.randint(2, 5) if unreliable else rng.choices([0, 1, 2, 3], [0.35, 0.42, 0.18, 0.05], k=1)[0],
            "performance": {"impressions": int(views * 1.12), "views": views, "engagements": engagements, "clicks": clicks, "conversions": conversions, "attributed_revenue_cny": revenue},
            "attribution_window_days": 14,
            "roi": round(revenue / amount, 4),
            "exclusive_until": iso(end + timedelta(days=rng.choice([0, 14, 30, 60, 90]))),
        })
    for account in accounts:
        profile = account["_history_profile"]
        if profile == "COLD_START":
            continue
        repeat_count = 5 if profile == "HISTORY_SUFFICIENT" else 1
        content_format = FORMATS[account["platform"]][0]
        for category in account["category_tags"]:
            for repeat in range(repeat_count):
                end = as_of - timedelta(days=35 + repeat * 21)
                views = max(
                    100,
                    int(account["follower_count_current"] * PLATFORM_VIEW_RATIO[account["platform"]]),
                )
                engagements = max(5, int(views * PLATFORM_ER[account["platform"]]))
                clicks = max(1, int(views * 0.015))
                conversions = max(0, int(clicks * 0.05))
                amount = max(1_000, int(account["follower_count_current"] * 0.025))
                revenue = round(conversions * 180.0, 2)
                rows.append({
                    "collaboration_id": f"col_{len(rows) + 1:06d}",
                    "account_id": account["account_id"],
                    "brand_name": BRANDS[category][repeat % len(BRANDS[category])],
                    "brand_category": category,
                    "started_at": iso(end - timedelta(days=21)),
                    "ended_at": iso(end),
                    "content_format": content_format,
                    "contract_amount_cny": amount,
                    "status": "completed",
                    "delivered_on_time": True,
                    "revision_count": repeat % 2,
                    "performance": {
                        "impressions": int(views * 1.12),
                        "views": views,
                        "engagements": engagements,
                        "clicks": clicks,
                        "conversions": conversions,
                        "attributed_revenue_cny": revenue,
                    },
                    "attribution_window_days": 14,
                    "roi": round(revenue / amount, 4),
                    "exclusive_until": iso(end),
                })
    return rows


def generate_policy_rules() -> list[dict]:
    return [
        {"rule_id": "rule_ad_disclosure", "version": "1.0", "type": "content_compliance", "description": "合作内容缺少可识别的广告标识线索", "default_action": "REVIEW", "is_legal_determination": False},
        {"rule_id": "rule_risky_claim", "version": "1.0", "type": "content_compliance", "description": "检测到需要结合上下文和证明材料复核的宣传表述", "default_action": "REVIEW", "is_legal_determination": False},
        {"rule_id": "rule_growth_anomaly", "version": "1.0", "type": "traffic_authenticity", "description": "短周期粉丝增长与互动质量不一致", "default_action": "REVIEW", "is_legal_determination": False},
        {"rule_id": "rule_reputation_spike", "version": "1.0", "type": "reputation", "description": "近期负面评论比例显著升高", "default_action": "REVIEW", "is_legal_determination": False},
        {"rule_id": "rule_competitor_exclusion", "version": "1.0", "type": "commercial_conflict", "description": "竞品合作仍处于品牌设定的排他窗口", "default_action": "BLOCK", "is_legal_determination": False},
        {"rule_id": "rule_delivery_reliability", "version": "1.0", "type": "delivery", "description": "历史延期或高修改次数达到审核阈值", "default_action": "REVIEW", "is_legal_determination": False},
    ]


def generate_risk_events(accounts: list[dict], evidence: list[dict], metrics: list[dict], contents: list[dict], collaborations: list[dict], as_of: date) -> list[dict]:
    rows = []
    evidence_by_account: dict[str, list[dict]] = defaultdict(list)
    for item in evidence:
        evidence_by_account[item["account_id"]].append(item)
    metrics_by_account: dict[str, list[dict]] = defaultdict(list)
    for item in metrics:
        metrics_by_account[item["account_id"]].append(item)
    contents_by_account: dict[str, list[dict]] = defaultdict(list)
    for item in contents:
        contents_by_account[item["account_id"]].append(item)
    collabs_by_account: dict[str, list[dict]] = defaultdict(list)
    for item in collaborations:
        collabs_by_account[item["account_id"]].append(item)

    def add(account_id: str, risk_type: str, subtype: str, severity: str, confidence: float, evidence_text: str, evidence_metric: dict, rule_id: str, content_id: str | None = None) -> None:
        rows.append({
            "risk_event_id": f"risk_{len(rows) + 1:06d}",
            "account_id": account_id,
            "content_id": content_id,
            "risk_type": risk_type,
            "risk_subtype": subtype,
            "observed_at": iso(as_of),
            "severity": severity,
            "confidence": round(confidence, 3),
            "evidence_text": evidence_text,
            "evidence_metric": evidence_metric,
            "source_url": None,
            "rule_id": rule_id,
            "rule_version": "1.0",
            "decision": "REVIEW",
            "review_status": "pending",
            "reviewer_action": None,
            "is_false_positive": None,
            "expires_at": iso(as_of + timedelta(days=30)),
        })

    for account in accounts:
        aid = account["account_id"]
        scenarios = set(account["_scenario"])
        if "fake_growth_burst" in scenarios:
            series = sorted(metrics_by_account[aid], key=lambda x: x["snapshot_date"])
            growths = [(series[i]["follower_count"] - series[i-1]["follower_count"]) / series[i-1]["follower_count"] for i in range(1, len(series))]
            add(aid, "traffic_authenticity", "growth_anomaly", "high", 0.92, "周粉丝增长突变且重复评论比例升高", {"max_weekly_growth": round(max(growths), 4), "max_repetitive_comment_ratio": max(x["repetitive_comment_ratio_observed"] for x in series)}, "rule_growth_anomaly")
        if "reputation_crisis" in scenarios:
            recent = [x for x in contents_by_account[aid] if x["published_at"] >= iso(as_of - timedelta(days=24))]
            ratio = sum(x["comment_sentiment"]["negative_ratio"] for x in recent) / max(1, len(recent))
            add(aid, "reputation", "negative_comment_spike", "high" if ratio > 0.6 else "medium", 0.88, "近24天负面评论比例异常上升", {"recent_negative_ratio": round(ratio, 4), "content_count": len(recent)}, "rule_reputation_spike")
        for item in evidence_by_account[aid][:3]:
            if item["scenario"] == "missing_ad_disclosure":
                add(aid, "content_compliance", "ad_disclosure_missing", "medium", 0.90, item["evidence"], {}, "rule_ad_disclosure", item["content_id"])
            elif item["scenario"] == "risky_claim":
                add(aid, "content_compliance", "claim_requires_review", "medium", 0.82, f"检测到待复核表述：{item['evidence']}", {"matched_phrase": item["evidence"]}, "rule_risky_claim", item["content_id"])
        if "delivery_unreliable" in scenarios:
            history = collabs_by_account[aid]
            if history:
                late_ratio = 1 - sum(x["delivered_on_time"] for x in history) / len(history)
                avg_revisions = sum(x["revision_count"] for x in history) / len(history)
                add(aid, "delivery", "delivery_reliability", "medium", 0.86, "历史合作延期或修改次数偏高", {"late_ratio": round(late_ratio, 4), "avg_revision_count": round(avg_revisions, 2), "sample_size": len(history)}, "rule_delivery_reliability")
    return rows


def generate_briefs(rng: random.Random, as_of: date, count: int) -> list[dict]:
    rows = []
    objectives = [("awareness", "impressions"), ("engagement", "engagements"), ("conversion", "conversions")]
    for idx in range(1, count + 1):
        category = rng.choice(CATEGORIES)
        brand = rng.choice(BRANDS[category])
        objective, kpi = rng.choice(objectives)
        platforms = rng.sample(PLATFORMS, k=rng.choice([1, 1, 2]))
        start = as_of + timedelta(days=rng.randint(14, 90))
        creator_count = rng.randint(3, 10)
        budget = rng.choice([60_000, 100_000, 150_000, 250_000, 400_000, 600_000])
        tone = rng.sample(STYLES, k=rng.choice([1, 2]))
        target_age = rng.choice(["18_24", "25_34", "35_44"])
        target_gender = rng.choice(["female", "female", "male", "balanced"])
        competitors = [b for b in BRANDS[category] if b != brand]
        rows.append({
            "campaign_id": f"cmp_{idx:04d}",
            "brand_name": brand,
            "product_name": f"{brand}{rng.choice(['新品', '旗舰系列', '限定套装', '入门款'])}",
            "product_category": category,
            "campaign_objective": objective,
            "primary_kpi": kpi,
            "target_platforms": platforms,
            "target_regions": rng.sample(REGIONS, k=rng.randint(3, 6)),
            "target_audience": {"gender_preference": target_gender, "primary_age_band": target_age, "interest_tags": rng.sample(INTERESTS, k=3)},
            "tone_tags": tone,
            "required_topics": rng.sample(TOPICS[category], k=2),
            "forbidden_topics": rng.sample(["夸大承诺", "贬低竞品", "敏感社会议题", "未成年人不当引导"], k=2),
            "content_formats": list({rng.choice(FORMATS[p]) for p in platforms}),
            "deliverables_per_creator": 1,
            "campaign_start_at": iso(start),
            "campaign_end_at": iso(start + timedelta(days=rng.randint(20, 45))),
            "total_budget_cny": budget,
            "max_budget_per_creator_cny": int(budget / max(2, creator_count - 1)),
            "creator_count": creator_count,
            "preferred_creator_tiers": rng.sample(["micro", "mid", "macro"], k=2),
            "competitor_brands": rng.sample(competitors, k=min(2, len(competitors))),
            "competitor_exclusion_days": rng.choice([30, 60, 90]),
            "usage_rights_days": rng.choice([30, 60, 90]),
            "exclusivity_required_days": rng.choice([0, 14, 30]),
            "risk_tolerance": rng.choice(["low", "medium"]),
            "brief_text": f"为{brand}推广{category}新品，目标是{objective}，面向{target_age}人群，整体调性为{'、'.join(tone)}，预算{budget}元。",
            "created_at": iso(as_of),
        })
    return rows


def generate_evaluation_labels(briefs: list[dict], accounts: list[dict], audience: list[dict], rates: list[dict], collaborations: list[dict], risk_events: list[dict], as_of: date) -> tuple[list[dict], list[dict]]:
    latest_audience: dict[str, dict] = {}
    for row in audience:
        if row["account_id"] not in latest_audience or row["snapshot_date"] > latest_audience[row["account_id"]]["snapshot_date"]:
            latest_audience[row["account_id"]] = row
    rates_by_account: dict[str, list[dict]] = defaultdict(list)
    for row in rates:
        rates_by_account[row["account_id"]].append(row)
    collabs_by_account: dict[str, list[dict]] = defaultdict(list)
    for row in collaborations:
        collabs_by_account[row["account_id"]].append(row)
    risks_by_account = Counter(row["account_id"] for row in risk_events if row["severity"] == "high")

    labels = []
    for brief in briefs:
        for account in accounts:
            reasons = []
            eligible = True
            if account["platform"] not in brief["target_platforms"]:
                eligible = False
                reasons.append("platform_mismatch")
            available_rates = [r for r in rates_by_account[account["account_id"]] if r["content_format"] in brief["content_formats"]]
            min_price = min((r["base_price_cny"] for r in available_rates), default=10**12)
            if min_price > brief["max_budget_per_creator_cny"]:
                eligible = False
                reasons.append("over_per_creator_budget")

            category_fit = 1.0 if brief["product_category"] == account["primary_category"] else (0.55 if brief["product_category"] in account["category_tags"] else 0.12)
            style_fit = len(set(brief["tone_tags"]) & set(account["style_tags"])) / max(1, len(brief["tone_tags"]))
            aud = latest_audience[account["account_id"]]
            age_fit = aud["audience_age_distribution"].get(brief["target_audience"]["primary_age_band"], 0)
            gender_pref = brief["target_audience"]["gender_preference"]
            gender_fit = 0.5 if gender_pref == "balanced" else aud["audience_gender_distribution"].get(gender_pref, 0)
            audience_fit = clamp(age_fit * 1.5 + gender_fit * 0.6, 0, 1)
            history = collabs_by_account[account["account_id"]]
            same_category = [c for c in history if c["brand_category"] == brief["product_category"]]
            brand_experience = clamp(len(same_category) / 4, 0, 1)
            performance = clamp(sum(c["roi"] for c in same_category[-5:]) / max(1, len(same_category[-5:])) / 2.5, 0, 1)
            cost_fit = clamp(1 - min_price / max(1, brief["max_budget_per_creator_cny"]), 0, 1)

            conflict = False
            conflict_brands = []
            for collab in history:
                if collab["brand_name"] in brief["competitor_brands"]:
                    days_since = (as_of - date.fromisoformat(collab["ended_at"])).days
                    if days_since <= brief["competitor_exclusion_days"] or date.fromisoformat(collab["exclusive_until"]) >= as_of:
                        conflict = True
                        conflict_brands.append(collab["brand_name"])
            if conflict:
                eligible = False
                reasons.append("competitor_exclusion_conflict")

            fit = 0.26 * category_fit + 0.18 * style_fit + 0.22 * audience_fit + 0.13 * brand_experience + 0.13 * performance + 0.08 * cost_fit
            high_risk = risks_by_account[account["account_id"]] > 0
            if high_risk and brief["risk_tolerance"] == "low":
                reasons.append("high_risk_requires_review")
            labels.append({
                "campaign_id": brief["campaign_id"],
                "account_id": account["account_id"],
                "eligible_ground_truth": eligible,
                "relevance_grade": 0,
                "fit_score_ground_truth": round(fit, 4),
                "component_ground_truth": {"category_fit": round(category_fit, 4), "style_fit": round(style_fit, 4), "audience_fit": round(audience_fit, 4), "brand_experience": round(brand_experience, 4), "performance": round(performance, 4), "cost_fit": round(cost_fit, 4)},
                "exclusion_reasons": sorted(set(reasons)),
                "competitor_conflict_ground_truth": conflict,
                "conflict_brands": sorted(set(conflict_brands)),
                "high_risk_review_ground_truth": high_risk,
                "label_source": "synthetic_rule_oracle_v1",
            })
    # Assign ranking grades within each brief. Relative grades guarantee that
    # every brief has useful positives while the absolute oracle score remains
    # available for calibration tests.
    labels_by_campaign: dict[str, list[dict]] = defaultdict(list)
    for label in labels:
        if label["eligible_ground_truth"]:
            labels_by_campaign[label["campaign_id"]].append(label)
    for campaign_labels in labels_by_campaign.values():
        campaign_labels.sort(key=lambda item: item["fit_score_ground_truth"], reverse=True)
        size = len(campaign_labels)
        grade3_end = max(5, math.ceil(size * 0.10))
        grade2_end = max(grade3_end + 5, math.ceil(size * 0.30))
        grade1_end = max(grade2_end + 5, math.ceil(size * 0.60))
        for rank, label in enumerate(campaign_labels):
            label["relevance_grade"] = 3 if rank < grade3_end else 2 if rank < grade2_end else 1 if rank < grade1_end else 0

    scenario_labels = [{"account_id": a["account_id"], "scenario_labels": a["_scenario"], "use_for_training": False, "purpose": "offline_risk_evaluation_only"} for a in accounts]
    return labels, scenario_labels


def public_accounts(accounts: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if not k.startswith("_")} for row in accounts]


def history_profile_labels(accounts: list[dict]) -> list[dict]:
    return [
        {
            "account_id": account["account_id"],
            "expected_history_profile": account["_history_profile"],
            "use_for_training": False,
            "purpose": "manual_and_offline_history_availability_evaluation",
        }
        for account in accounts
    ]


def generate_history_availability_scenarios(as_of: date) -> list[dict]:
    """Small deterministic oracle set for cold-start tier regression tests."""
    base = {
        "campaign_category": "食品饮料",
        "compatible_formats": ["图文"],
        "primary_kpi": "conversions",
        "evaluated_at": iso(as_of),
        "use_for_training": False,
    }

    def collaboration(index: int, *, status: str = "completed", include_kpi: bool = True) -> dict:
        performance = {"views": 10_000}
        if include_kpi:
            performance["conversions"] = 12
        return {
            "collaboration_id": f"history_fixture_{index:02d}",
            "brand_category": "食品饮料",
            "content_format": "图文",
            "ended_at": iso(as_of - timedelta(days=45 + index * 30)),
            "status": status,
            "performance": performance,
            "attribution_window_days": 14,
        }

    return [
        {
            **base,
            "scenario_id": "history_sufficient",
            "collaborations": [collaboration(1), collaboration(2), collaboration(3)],
            "expected_tier": "HISTORY_SUFFICIENT",
            "expected_effective_history_n": 3.0,
        },
        {
            **base,
            "scenario_id": "history_limited",
            "collaborations": [collaboration(4)],
            "expected_tier": "HISTORY_LIMITED",
            "expected_effective_history_n": 1.0,
        },
        {
            **base,
            "scenario_id": "cold_start",
            "collaborations": [collaboration(5, include_kpi=False)],
            "expected_tier": "COLD_START",
            "expected_effective_history_n": 0.0,
        },
    ]


def validate(data: dict[str, list[dict]]) -> dict[str, Any]:
    errors: list[str] = []
    creator_ids = {x["creator_id"] for x in data["creators"]}
    account_ids = {x["account_id"] for x in data["accounts"]}
    if len(creator_ids) != len(data["creators"]):
        errors.append("duplicate creator_id")
    if len(account_ids) != len(data["accounts"]):
        errors.append("duplicate account_id")
    for account in data["accounts"]:
        if account["creator_id"] not in creator_ids:
            errors.append(f"missing creator FK: {account['account_id']}")
    for table in ["audience_snapshots", "account_metric_snapshots", "content_items", "rate_cards", "collaborations", "risk_events"]:
        for row in data[table]:
            if row["account_id"] not in account_ids:
                errors.append(f"missing account FK in {table}")
                break
    for content in data["content_items"]:
        if any(v < 0 for v in content["metrics"].values()):
            errors.append(f"negative content metric: {content['content_id']}")
            break
        if content["metrics"]["impressions"] < content["metrics"]["views"]:
            errors.append(f"impressions below views: {content['content_id']}")
            break
    for audience in data["audience_snapshots"]:
        for field in ["audience_gender_distribution", "audience_age_distribution"]:
            if abs(sum(audience[field].values()) - 1.0) > 0.002:
                errors.append(f"distribution does not sum to 1: {audience['account_id']} {field}")
                break
    return {
        "valid": not errors,
        "errors": errors[:25],
        "row_counts": {name: len(rows) for name, rows in data.items()},
    }


def build_dataset(output_dir: Path, seed: int, as_of: date, creator_count: int, brief_count: int) -> dict[str, Any]:
    rng = random.Random(seed)
    creators, accounts = generate_entities(rng, creator_count, as_of)
    assign_scenarios(rng, accounts)
    audience = generate_audience_snapshots(rng, accounts, as_of)
    metrics = generate_metric_snapshots(rng, accounts, as_of)
    contents, evidence = generate_contents(rng, accounts, as_of)
    rates = generate_rate_cards(rng, accounts, as_of)
    collaborations = generate_collaborations(rng, accounts, as_of, target_count=max(700, creator_count * 3))
    policies = generate_policy_rules()
    risks = generate_risk_events(accounts, evidence, metrics, contents, collaborations, as_of)
    briefs = generate_briefs(rng, as_of, brief_count)
    labels, scenario_labels = generate_evaluation_labels(briefs, accounts, audience, rates, collaborations, risks, as_of)

    data = {
        "creators": creators,
        "accounts": public_accounts(accounts),
        "audience_snapshots": audience,
        "account_metric_snapshots": metrics,
        "content_items": contents,
        "rate_cards": rates,
        "collaborations": collaborations,
        "risk_events": risks,
        "campaign_briefs": briefs,
    }
    report = validate(data)
    if not report["valid"]:
        raise RuntimeError("Dataset validation failed: " + "; ".join(report["errors"]))

    if output_dir.exists():
        shutil.rmtree(output_dir)
    evaluation_dir = output_dir / "evaluation"
    output_dir.mkdir(parents=True)
    evaluation_dir.mkdir()
    for name, rows in data.items():
        write_jsonl(output_dir / f"{name}.jsonl", rows)
    write_json(output_dir / "policy_rules.json", policies)
    write_jsonl(evaluation_dir / "relevance_labels.jsonl", labels)
    write_jsonl(evaluation_dir / "risk_scenario_ground_truth.jsonl", scenario_labels)
    history_scenarios = generate_history_availability_scenarios(as_of)
    write_jsonl(evaluation_dir / "history_availability_ground_truth.jsonl", history_scenarios)
    profile_labels = history_profile_labels(accounts)
    write_jsonl(evaluation_dir / "history_profile_ground_truth.jsonl", profile_labels)
    write_json(evaluation_dir / "validation_report.json", report)

    scenario_counts = Counter(label for account in accounts for label in account["_scenario"])
    history_profile_counts = Counter(account["_history_profile"] for account in accounts)
    manifest = {
        "dataset_name": "creator_match_risk_synthetic_v1",
        "generated_at": iso(as_of),
        "as_of_date": iso(as_of),
        "seed": seed,
        "is_synthetic": True,
        "contains_real_personal_data": False,
        "production_tables_must_not_include_evaluation_labels": True,
        "row_counts": {**report["row_counts"], "policy_rules": len(policies), "evaluation_relevance_labels": len(labels), "evaluation_risk_scenario_labels": len(scenario_labels), "evaluation_history_availability_scenarios": len(history_scenarios), "evaluation_history_profile_labels": len(profile_labels)},
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "history_profile_counts": dict(sorted(history_profile_counts.items())),
        "notes": [
            "All names, brands, profiles, content and metrics are fictional.",
            "Risk events are review leads, not legal determinations.",
            "Files under evaluation contain oracle labels and must not be used as recommendation inputs.",
            "History availability evaluation includes deterministic sufficient, limited and cold-start cases.",
        ],
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data"), help="Output directory")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF)
    parser.add_argument("--creators", type=int, default=320)
    parser.add_argument("--briefs", type=int, default=50)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_dataset(args.output.resolve(), args.seed, args.as_of, args.creators, args.briefs)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
