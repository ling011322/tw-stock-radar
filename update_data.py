import json
import urllib.request
from datetime import datetime

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
    """把證交所文字資料安全轉成數字"""
    if value is None:
        return None

    value = str(value).replace(",", "").strip()

    if value in ["", "-", "--", "N/A"]:
        return None

    try:
        return float(value)
    except:
        return None


print("開始取得台股資料...")

# ① 每日行情
prices = get_json("/exchangeReport/STOCK_DAY_ALL")

# ② PE / 殖利率 / PB
valuation = get_json("/exchangeReport/BWIBBU_ALL")

print(f"行情資料：{len(prices)} 筆")
print(f"估值資料：{len(valuation)} 筆")


# 建立估值資料索引
valuation_map = {}

for item in valuation:

    code = item.get("Code")

    if code:
        valuation_map[code] = item


results = []

for stock in prices:

    code = stock.get("Code")
    name = stock.get("Name")

    # 只處理一般四碼股票
    if not code or len(code) != 4 or not code.isdigit():
        continue

    close = number(stock.get("ClosingPrice"))
    volume = number(stock.get("TradeVolume"))
    change = number(stock.get("Change"))

    if close is None or close <= 0:
        continue

    value_data = valuation_map.get(code, {})

    pe = number(value_data.get("PEratio"))
    dividend_yield = number(value_data.get("DividendYield"))
    pb = number(value_data.get("PBratio"))

    # ==============================
    # 長期投資評分
    # ==============================

    score = 50
    reasons = []

    # ----- 本益比 -----

    if pe is not None:

        if 0 < pe <= 12:
            score += 15
            reasons.append("本益比偏低")

        elif pe <= 18:
            score += 10
            reasons.append("本益比合理")

        elif pe <= 25:
            score += 5

        elif pe > 40:
            score -= 10
            reasons.append("本益比較高")


    # ----- 殖利率 -----

    if dividend_yield is not None:

        if dividend_yield >= 5:
            score += 15
            reasons.append("殖利率具吸引力")

        elif dividend_yield >= 3:
            score += 10
            reasons.append("殖利率不錯")

        elif dividend_yield >= 2:
            score += 5


    # ----- PB -----

    if pb is not None:

        if 0 < pb <= 1.5:
            score += 10
            reasons.append("股價淨值比偏低")

        elif pb <= 2.5:
            score += 5

        elif pb >= 6:
            score -= 5


    # ----- 流動性 -----

    if volume is not None:

        if volume >= 5_000_000:
            score += 5
            reasons.append("成交流動性佳")

        elif volume < 100_000:
            score -= 10


    # 分數限制
    score = max(0, min(100, score))


    # ==============================
    # 價格觀察區
    # ==============================

    # 第一版先採簡單規則
    # 不是預測未來股價

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

        "reasons": reasons[:4]

    })


# ==============================
# 基本流動性篩選
# ==============================

eligible = [

    x for x in results

    if x["volume"] is not None
    and x["volume"] >= 500_000

]


# ==============================
# 長期 TOP 5
# ==============================

long_term_top5 = sorted(
    eligible,
    key=lambda x: x["long_score"],
    reverse=True
)[:5]


print("\n長期投資 TOP 5")

for stock in long_term_top5:

    print(
        stock["code"],
        stock["name"],
        stock["long_score"],
        stock["price"]
    )


# ==============================
# 儲存網站資料
# ==============================

output = {

    "updated_at":
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

    "source":
        "Taiwan Stock Exchange OpenAPI",

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
