import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = "https://openapi.twse.com.tw/v1"


def get_json(path):
    url = BASE + path

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def number(value):
    if value is None:
        return None

    value = str(value).replace(",", "").replace("%", "").strip()

    if value in ["", "-", "--", "N/A"]:
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


print("開始取得台股資料...")


# ==========================================
# 1. 每日行情
# ==========================================

prices = get_json("/exchangeReport/STOCK_DAY_ALL")

print(f"行情資料：{len(prices)} 筆")


# ==========================================
# 2. PE / 殖利率 / PB
# ==========================================

valuation = get_json("/exchangeReport/BWIBBU_ALL")

print(f"估值資料：{len(valuation)} 筆")


valuation_map = {}

for item in valuation:
    code = item.get("Code")

    if code:
        valuation_map[code] = item


# ==========================================
# 3. 月營收資料
# ==========================================

revenue = get_json("/opendata/t187ap05_L")

print(f"月營收資料：{len(revenue)} 筆")


revenue_map = {}

for item in revenue:

    code = item.get("公司代號")

    if not code:
        continue

    yoy = number(item.get("去年同月增減(%)"))
    mom = number(item.get("上月比較增減(%)"))

    revenue_map[code] = {
        "revenue_yoy": yoy,
        "revenue_mom": mom
    }


# ==========================================
# 4. 整合股票資料
# ==========================================

results = []


for stock in prices:

    code = stock.get("Code")
    name = stock.get("Name")

    # 只保留一般四碼股票
    if not code or len(code) != 4 or not code.isdigit():
        continue

    close = number(stock.get("ClosingPrice"))
    volume = number(stock.get("TradeVolume"))
    change = number(stock.get("Change"))

    if close is None or close <= 0:
        continue


    # 估值資料
    value_data = valuation_map.get(code, {})

    pe = number(value_data.get("PEratio"))
    dividend_yield = number(value_data.get("DividendYield"))
    pb = number(value_data.get("PBratio"))


    # 營收資料
    revenue_data = revenue_map.get(code, {})

    revenue_yoy = revenue_data.get("revenue_yoy")
    revenue_mom = revenue_data.get("revenue_mom")


    # ======================================
    # 長期投資評分 V2
    # ======================================

    score = 50.0
    reasons = []


    # --------------------------------------
    # A. 營收成長
    # --------------------------------------

    if revenue_yoy is not None:

        if revenue_yoy >= 30:
            score += 20
            reasons.append("營收年增強勁")

        elif revenue_yoy >= 15:
            score += 15
            reasons.append("營收維持良好成長")

        elif revenue_yoy >= 5:
            score += 10
            reasons.append("營收穩定成長")

        elif revenue_yoy >= 0:
            score += 3
            reasons.append("營收大致穩定")

        elif revenue_yoy <= -20:
            score -= 15
            reasons.append("營收明顯衰退")

        elif revenue_yoy <= -10:
            score -= 10
            reasons.append("營收年增轉弱")


    # --------------------------------------
    # B. 本益比
    # --------------------------------------

    if pe is not None and pe > 0:

        if pe <= 10:
            score += 10
            reasons.append("本益比偏低")

        elif pe <= 18:
            score += 8
            reasons.append("本益比合理")

        elif pe <= 25:
            score += 4

        elif pe <= 35:
            score += 1

        elif pe > 50:
            score -= 5
            reasons.append("本益比較高")


    # --------------------------------------
    # C. 殖利率
    # --------------------------------------

    if dividend_yield is not None:

        if dividend_yield >= 5:
            score += 8
            reasons.append("殖利率具吸引力")

        elif dividend_yield >= 3:
            score += 5
            reasons.append("殖利率不錯")

        elif dividend_yield >= 1.5:
            score += 2


    # --------------------------------------
    # D. 股價淨值比
    # --------------------------------------

    if pb is not None and pb > 0:

        if pb <= 1.5:
            score += 6
            reasons.append("股價淨值比偏低")

        elif pb <= 3:
            score += 3

        # 高 PB 不直接重罰
        # 成長型公司本來就可能有較高 PB


    # --------------------------------------
    # E. 流動性
    # --------------------------------------

    if volume is not None:

        if volume >= 5_000_000:
            score += 5
            reasons.append("成交流動性佳")

        elif volume >= 1_000_000:
            score += 3

        elif volume < 100_000:
            score -= 10


    # --------------------------------------
    # 分數限制
    # --------------------------------------

    score = round(max(0, min(100, score)), 1)


    # ======================================
    # 暫時價格區間
    # ======================================
    #
    # 注意：
    # 目前只是觀察區，不是真正合理價。
    # 後續加入歷史價格與財報後會重新設計。
    # ======================================

    buy_low = round(close * 0.92, 2)
    buy_high = round(close * 0.97, 2)

    target_1 = round(close * 1.10, 2)
    target_2 = round(close * 1.20, 2)

    risk_price = round(close * 0.88, 2)


    results.append({
        "code": code,
        "name": name,

        "price": close,
        "change": change,
        "volume": volume,

        "pe": pe,
        "dividend_yield": dividend_yield,
        "pb": pb,

        "revenue_yoy": revenue_yoy,
        "revenue_mom": revenue_mom,

        "long_score": score,

        "buy_zone": [
            buy_low,
            buy_high
        ],

        "target_zone": [
            target_1,
            target_2
        ],

        "risk_price": risk_price,

        "reasons": reasons[:5]
    })


# ==========================================
# 5. 基本篩選
# ==========================================

eligible = [
    stock
    for stock in results
    if stock["volume"] is not None
    and stock["volume"] >= 500_000
]


# ==========================================
# 6. 長期 TOP 5
# ==========================================

long_term_top5 = sorted(
    eligible,
    key=lambda x: (
        x["long_score"],
        x["revenue_yoy"] if x["revenue_yoy"] is not None else -999
    ),
    reverse=True
)[:5]


print("\n===== 長期投資 TOP 5 =====")

for i, stock in enumerate(long_term_top5, start=1):

    print(
        i,
        stock["code"],
        stock["name"],
        "分數:",
        stock["long_score"],
        "營收YoY:",
        stock["revenue_yoy"]
    )


# ==========================================
# 7. 儲存網站資料
# ==========================================

taiwan_now = datetime.now(
    ZoneInfo("Asia/Taipei")
)


output = {
    "updated_at":
        taiwan_now.strftime("%Y-%m-%d %H:%M:%S"),

    "source":
        "Taiwan Stock Exchange OpenAPI",

    "model_version":
        "Long Term V2",

    "stock_count":
        len(results),

    "long_term_top5":
        long_term_top5,

    "stocks":
        results
}


with open(
    "stock_data.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        ensure_ascii=False,
        indent=2
    )


print("\nstock_data.json 更新完成")
