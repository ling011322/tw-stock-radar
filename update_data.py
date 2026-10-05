import json
import urllib.request
from datetime import datetime

# 台灣證券交易所 OpenAPI
URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

print("開始取得台灣證券交易所資料...")

request = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
)

with urllib.request.urlopen(request, timeout=30) as response:
    stocks = json.loads(response.read().decode("utf-8"))

print(f"成功取得 {len(stocks)} 筆股票資料")

# 找出台積電作為測試
tsmc = next(
    (stock for stock in stocks if stock.get("Code") == "2330"),
    None
)

if tsmc:
    print("成功找到 2330 台積電")
    print(tsmc)
else:
    print("找不到 2330，請檢查資料來源")

# 將資料存成 JSON，未來網站會讀這個檔案
output = {
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "source": "Taiwan Stock Exchange OpenAPI",
    "stock_count": len(stocks),
    "test_stock": tsmc
}

with open("stock_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("stock_data.json 建立完成")
