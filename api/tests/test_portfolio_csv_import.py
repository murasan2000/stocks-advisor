"""楽天証券CSVパーサーのテスト（実際のサンプル形式を使用）。"""

from __future__ import annotations

from app.services.portfolio.csv_import import (
    ParsedHolding,
    decode_csv_bytes,
    merge_duplicate_codes,
    parse_rakuten_holdings_csv,
)

_SAMPLE_CSV = """\
■現在の評価額合計［円］,,"358,161"
■評価損益合計,前日比［円］,"2,589"
,前月比［円］,"-61,859"
,評価損益［円］,"-91,849"
■NISA成長投資枠

銘柄コード,銘柄名,保有数量［株］,執行中［株］,(内訳　保護預り数量[株]),(内訳　通常数量[株]),(内訳　積立数量[株]),(内訳　共有口座数量[株]),平均取得価額［円］,保護預り平均取得価額［円］,共有口座平均取得価額［円］,取得総額［円］,現在値［円］,現在値（前日比）［円］,時価評価額［円］,評価損益［円］,保護預り評価損益［円］,共有口座評価損益［円］
"1111","XXX鉱山","20","0","-","20","0","-","8,888.50","-","-","177,770","7,844.0","126.0","156,880","-20,890","-","-"
"2222","XXXホールディングス","32","0","-","2","30","-","3,441.81","-","-","110,138","2,908.0","5.5","93,056","-17,082","-","-"
"3333","株式会社XXX","15","0","-","0","15","-","10,806.80","-","-","162,102","7,215.0","-523.0","108,225","-53,877","-","-"
,,,,,,,,,,NISA成長投資枠口座合計,"450,010",,,"358,161","-91,849"
"""


def test_parse_rakuten_csv_extracts_all_rows() -> None:
    holdings = parse_rakuten_holdings_csv(_SAMPLE_CSV)
    assert holdings == [
        ParsedHolding("1111", "XXX鉱山", 20.0, 8888.50),
        ParsedHolding("2222", "XXXホールディングス", 32.0, 3441.81),
        ParsedHolding("3333", "株式会社XXX", 15.0, 10806.80),
    ]


def test_parse_rakuten_csv_skips_footer_and_summary_lines() -> None:
    holdings = parse_rakuten_holdings_csv(_SAMPLE_CSV)
    codes = [h.code for h in holdings]
    assert "NISA成長投資枠口座合計" not in codes
    assert len(holdings) == 3


def test_parse_rakuten_csv_handles_multiple_sections() -> None:
    # 特定口座セクションを追加し、複数セクションが横断的にパースされることを確認
    multi_section = _SAMPLE_CSV + (
        "\n■特定口座\n\n"
        "銘柄コード,銘柄名,保有数量［株］,執行中［株］,(内訳　保護預り数量[株]),"
        "(内訳　通常数量[株]),(内訳　積立数量[株]),(内訳　共有口座数量[株]),"
        "平均取得価額［円］,保護預り平均取得価額［円］,共有口座平均取得価額［円］,"
        "取得総額［円］,現在値［円］,現在値（前日比）［円］,時価評価額［円］,"
        "評価損益［円］,保護預り評価損益［円］,共有口座評価損益［円］\n"
        '"1111","XXX鉱山","10","0","-","10","0","-","9,000.00","-","-",'
        '"90,000","7,844.0","126.0","78,440","-11,560","-","-"\n'
        ',,,,,,,,,,特定口座合計,"78,440",,,"78,440","-11,560"\n'
    )
    holdings = parse_rakuten_holdings_csv(multi_section)
    # 1111 が2セクションに出現（統合前なのでそれぞれ別行のまま4件）
    assert len(holdings) == 4
    assert sum(1 for h in holdings if h.code == "1111") == 2


def test_parse_rakuten_csv_empty_input_returns_empty() -> None:
    assert parse_rakuten_holdings_csv("") == []


def test_parse_rakuten_csv_skips_zero_quantity_rows() -> None:
    # 手動登録（HoldingRequest）の gt=0 制約と揃え、数量/単価が0の行は取り込まない
    header = "銘柄コード,銘柄名,保有数量［株］,平均取得価額［円］\n"
    csv_text = header + '"9999","全株売却済み","0","1,000.00"\n'
    assert parse_rakuten_holdings_csv(csv_text) == []


def test_merge_duplicate_codes_weighted_average() -> None:
    holdings = [
        ParsedHolding("1111", "XXX鉱山", 20.0, 8888.50),
        ParsedHolding("1111", "XXX鉱山", 10.0, 9000.00),
    ]
    merged = merge_duplicate_codes(holdings)
    assert len(merged) == 1
    assert merged[0].quantity == 30.0
    expected_avg = (20.0 * 8888.50 + 10.0 * 9000.00) / 30.0
    assert merged[0].avg_cost == expected_avg


def test_merge_duplicate_codes_no_duplicates_unchanged() -> None:
    holdings = [
        ParsedHolding("1111", "XXX鉱山", 20.0, 8888.50),
        ParsedHolding("2222", "XXXホールディングス", 32.0, 3441.81),
    ]
    merged = merge_duplicate_codes(holdings)
    assert merged == holdings


def test_decode_csv_bytes_utf8() -> None:
    assert decode_csv_bytes("銘柄コード".encode()) == "銘柄コード"


def test_decode_csv_bytes_utf8_sig_strips_bom() -> None:
    data = "銘柄コード".encode("utf-8-sig")
    assert decode_csv_bytes(data) == "銘柄コード"


def test_decode_csv_bytes_cp932_fallback() -> None:
    data = "銘柄コード".encode("cp932")
    assert decode_csv_bytes(data) == "銘柄コード"


# ---------------------------------------------------------------------------
# 米国株セクション（ティッカー始まり・USドル建て。換算はせずドルのまま保持する）
# ---------------------------------------------------------------------------

_US_SAMPLE_CSV = """\
■時価評価額合計［USドル］,"1,981.25",■前日比合計［USドル］,"-76.67",■評価損益額合計［USドル］,"-61.08",,時間外株価を含まない
■円換算時価評価額合計,"320,723",■円換算前日比合計,"-12,701",■円換算評価損益額合計,"-6,979",,"参考為替レート(米ドル)","161.88","円/USD","07/14 22:10"

■NISA成長投資枠

ティッカー,銘柄名,取引所,保有数量［株］,執行中数量［株］,(内訳 通常数量[株]),(内訳 積立数量[株]),表示通貨,平均取得価額［USドル］,取得総額［USドル］,現在値［USドル］,前日比［USドル］,時価評価額［USドル］,評価損益［USドル］
"HOGE","ホゲホゲ","米国市場","7","-","-","-","USドル","214.6200","1,502.34","203.5284","0.00","1,424.69","-77.64"
"FUGA","フガフガ","米国市場","4","-","-","-","USドル","135.0000","540.00","139.1400","0.00","556.56","16.56"
"""


def test_parse_rakuten_csv_us_section_keeps_native_usd() -> None:
    # 円換算はせず、CSVに記載されたUSドルの値をそのまま保持する
    holdings = parse_rakuten_holdings_csv(_US_SAMPLE_CSV)
    assert holdings == [
        ParsedHolding("HOGE", "ホゲホゲ", 7.0, 214.62),
        ParsedHolding("FUGA", "フガフガ", 4.0, 135.00),
    ]


def test_parse_rakuten_csv_mixed_jp_us_sections() -> None:
    # JP・US両セクションを含むファイルを横断的にパースする（通貨は変換せずそれぞれ保持）
    combined = _SAMPLE_CSV + "\n" + _US_SAMPLE_CSV
    holdings = parse_rakuten_holdings_csv(combined)
    codes = {h.code for h in holdings}
    assert codes == {"1111", "2222", "3333", "HOGE", "FUGA"}


def test_parse_rakuten_csv_us_skips_zero_quantity_rows() -> None:
    # 手動登録と同じ gt=0 制約は米国株セクションにも適用される
    header = "ティッカー,銘柄名,保有数量［株］,平均取得価額［USドル］\n"
    csv_text = header + '"ZERO","全株売却済み","0","100.00"\n'
    assert parse_rakuten_holdings_csv(csv_text) == []


def test_parse_rakuten_csv_us_ticker_code_normalized_to_uppercase() -> None:
    # 手動登録（HoldingsRepository）と同じ正規化をパース時点で行い、
    # 大文字小文字違いのティッカーがmerge_duplicate_codesで正しく統合されるようにする。
    header = "ティッカー,銘柄名,保有数量［株］,平均取得価額［USドル］\n"
    csv_text = header + '"hoge","ホゲホゲ","7","100.00"\n'
    holdings = parse_rakuten_holdings_csv(csv_text)
    assert holdings == [ParsedHolding("HOGE", "ホゲホゲ", 7.0, 100.00)]


def test_merge_duplicate_codes_case_insensitive_after_parse() -> None:
    # 複数セクションに大文字小文字違いで同一ティッカーが出現しても、
    # parse_rakuten_holdings_csv側で正規化済みのため正しく統合される。
    header = "ティッカー,銘柄名,保有数量［株］,平均取得価額［USドル］\n"
    section_a = header + '"hoge","ホゲホゲ","5","100.00"\n'
    section_b = header + '"HOGE","ホゲホゲ","5","200.00"\n'
    holdings = merge_duplicate_codes(
        parse_rakuten_holdings_csv(section_a + "\n" + section_b)
    )
    assert len(holdings) == 1
    assert holdings[0].code == "HOGE"
    assert holdings[0].quantity == 10.0
    expected_avg = (5 * 100.00 + 5 * 200.00) / 10.0
    assert holdings[0].avg_cost == expected_avg
