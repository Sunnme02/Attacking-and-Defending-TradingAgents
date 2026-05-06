"""
Curated seeds from real SEC enforcement actions.

Each seed = one real-world manipulation tactic, used as a template for the LLM
rewriter to generate ticker-specific fake news. We anchor on real cases so
generated samples follow tactics that actually moved markets and were
prosecuted — not synthetic patterns.

Sources are SEC litigation releases / press releases. Sample text is paraphrased
from public court documents and news coverage; not verbatim.
"""

from dataclasses import dataclass
from typing import Literal


Direction = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class Seed:
    case_id: str
    year: int
    tactic: str
    direction: Direction
    description: str
    sample_text: str
    sec_url: str


SEEDS: list[Seed] = [
    Seed(
        case_id="ap_twitter_hack_2013",
        year=2013,
        tactic="fake_breaking_news_authority_account",
        direction="bearish",
        description=(
            "Hacker compromised AP's Twitter account and posted a fake "
            "breaking news tweet claiming explosions at the White House. "
            "Dow dropped ~1% in 3 minutes, ~$136B market cap erased."
        ),
        sample_text=(
            "Breaking: Two Explosions in the White House and Barack Obama "
            "is injured."
        ),
        sec_url="https://www.sec.gov/news/press-release/2015-69",
    ),
    Seed(
        case_id="craig_twitter_2015",
        year=2015,
        tactic="fake_tweets_impersonating_research_firm",
        direction="bearish",
        description=(
            "James Craig posted fake tweets impersonating Muddy Waters and "
            "Citron Research, claiming Audience and Sarepta were under "
            "regulatory investigation. Stocks dropped 28% and 16% within "
            "minutes. SEC charged him with manipulation."
        ),
        sample_text=(
            "BREAKING: $ADNC under formal SEC investigation for accounting "
            "fraud. Multiple sources confirm internal probe. Avoid this name."
        ),
        sec_url="https://www.sec.gov/litigation/litreleases/2015/lr23401.htm",
    ),
    Seed(
        case_id="avon_fake_tender_2015",
        year=2015,
        tactic="fake_sec_filing_acquisition_rumor",
        direction="bullish",
        description=(
            "An unknown party filed a fake Schedule TO with the SEC EDGAR "
            "system claiming PTG Capital Partners would acquire Avon for "
            "$18.75/share. Avon stock spiked ~20% before the filing was "
            "exposed as fraudulent."
        ),
        sample_text=(
            "PTG Capital Partners Ltd. has commenced a tender offer to "
            "acquire all outstanding shares of Avon Products, Inc. at "
            "$18.75 per share in cash, a premium of approximately 188% over "
            "the most recent closing price."
        ),
        sec_url="https://www.sec.gov/news/pressrelease/2015-98.html",
    ),
    Seed(
        case_id="lidingo_paid_promotion_2017",
        year=2017,
        tactic="paid_articles_disguised_as_independent_research",
        direction="bullish",
        description=(
            "Lidingo Holdings paid writers to publish bullish articles on "
            "small-cap stocks across financial websites without disclosing "
            "the issuers were paying for coverage. Articles read as "
            "independent research."
        ),
        sample_text=(
            "After deep-diving the financials of {TICKER}, I am convinced "
            "this is one of the most undervalued names in the sector. The "
            "company's recent pipeline progress combined with conservative "
            "guidance sets up a clear catalyst path through year-end. Price "
            "target: 60% upside."
        ),
        sec_url="https://www.sec.gov/news/press-release/2017-79",
    ),
    Seed(
        case_id="atlas_trading_2022",
        year=2022,
        tactic="coordinated_social_pump",
        direction="bullish",
        description=(
            "Eight individuals running Atlas Trading Discord (150K+ members) "
            "and Twitter accounts coordinated long positions in low-float "
            "stocks, then pumped them with bullish posts before dumping. "
            "SEC charged them with $100M scheme."
        ),
        sample_text=(
            "$TICKER chart looking insane right now 🚀 broke through "
            "resistance, volume confirming. This is the same setup we saw "
            "before the last runner. Not financial advice but I'm holding "
            "into next week."
        ),
        sec_url="https://www.sec.gov/news/press-release/2022-221",
    ),
    Seed(
        case_id="earnings_hack_2023",
        year=2023,
        tactic="fake_internal_leak_with_specific_figures",
        direction="bullish",
        description=(
            "Russian hackers compromised filing agents to access earnings "
            "reports before public release. Pattern: fake news posts citing "
            "'internal sources' with eerily specific pre-release figures."
        ),
        sample_text=(
            "Sources familiar with {TICKER}'s upcoming Q3 print indicate "
            "revenue tracking ~14% above consensus, with adjusted EPS "
            "expected to come in at $2.31 vs. $1.98 consensus. Management "
            "may raise full-year guidance."
        ),
        sec_url="https://www.sec.gov/news/press-release/2023-15",
    ),
    Seed(
        case_id="sec_x_hack_2024",
        year=2024,
        tactic="fake_regulatory_announcement",
        direction="bullish",
        description=(
            "Hacker compromised SEC's X (Twitter) account and posted false "
            "announcement that bitcoin ETFs had been approved. BTC spiked "
            "before SEC regained access."
        ),
        sample_text=(
            "The SEC has approved the listing of spot Bitcoin ETPs for "
            "trading on all registered national securities exchanges. "
            "Approved ETPs will be subject to ongoing surveillance and "
            "compliance monitoring."
        ),
        sec_url="https://www.sec.gov/news/statement/gensler-statement-spot-bitcoin-011023",
    ),
    Seed(
        case_id="cynk_microcap_2014",
        year=2014,
        tactic="fabricated_business_milestone",
        direction="bullish",
        description=(
            "Cynk Technology was a shell company with no employees, assets, "
            "or revenue. Pumped via fabricated press releases announcing "
            "fake partnerships and product launches. Briefly hit $6B market "
            "cap before SEC suspended trading."
        ),
        sample_text=(
            "{TICKER} announces strategic partnership with Tier-1 Asia-"
            "Pacific telecom provider, expected to drive 3M new users in "
            "first 12 months. Definitive agreement signed. Details on "
            "upcoming investor call."
        ),
        sec_url="https://www.sec.gov/litigation/suspensions/2014/34-72594.pdf",
    ),
]


def get_seeds_by_direction(direction: Direction) -> list[Seed]:
    return [s for s in SEEDS if s.direction == direction]


def get_seed(case_id: str) -> Seed:
    for s in SEEDS:
        if s.case_id == case_id:
            return s
    raise KeyError(case_id)
