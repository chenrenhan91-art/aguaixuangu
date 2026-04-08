from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd
import requests
from akshare.stock_feature.stock_board_industry_ths import (
    stock_board_industry_name_ths,
    stock_board_industry_summary_ths,
)
from curl_cffi import requests as curl_requests

from data_pipeline.adapters.akshare_client import run_without_proxy


FALLBACK_INDUSTRY_ROWS = [
    {
        "排名": 1,
        "板块名称": "氮肥",
        "板块代码": "BK1432",
        "最新价": 2338.99,
        "涨跌额": 167.54,
        "涨跌幅": 7.72,
        "总市值": 124543498000,
        "换手率": 4.64,
        "上涨家数": 6,
        "下跌家数": 0,
        "领涨股票": "潞化科技",
        "领涨股票-涨跌幅": 9.87,
        "总成交额": 0.0,
        "净流入": 0.0,
    },
    {
        "排名": 2,
        "板块名称": "有机硅",
        "板块代码": "BK1431",
        "最新价": 3289.76,
        "涨跌额": 205.13,
        "涨跌幅": 6.65,
        "总市值": 112612126000,
        "换手率": 2.19,
        "上涨家数": 10,
        "下跌家数": 0,
        "领涨股票": "东岳硅材",
        "领涨股票-涨跌幅": 19.98,
        "总成交额": 0.0,
        "净流入": 0.0,
    },
    {
        "排名": 3,
        "板块名称": "煤化工",
        "板块代码": "BK1419",
        "最新价": 2172.16,
        "涨跌额": 126.76,
        "涨跌幅": 6.2,
        "总市值": 329059360000,
        "换手率": 2.77,
        "上涨家数": 10,
        "下跌家数": 0,
        "领涨股票": "诚志股份",
        "领涨股票-涨跌幅": 9.99,
        "总成交额": 0.0,
        "净流入": 0.0,
    },
    {
        "排名": 4,
        "板块名称": "动物保健Ⅱ",
        "板块代码": "BK1254",
        "最新价": 4988.73,
        "涨跌额": 284.06,
        "涨跌幅": 6.04,
        "总市值": 74112166000,
        "换手率": 2.97,
        "上涨家数": 12,
        "下跌家数": 1,
        "领涨股票": "申联生物",
        "领涨股票-涨跌幅": 20.0,
        "总成交额": 0.0,
        "净流入": 0.0,
    },
    {
        "排名": 5,
        "板块名称": "动物保健Ⅲ",
        "板块代码": "BK1501",
        "最新价": 4988.73,
        "涨跌额": 284.06,
        "涨跌幅": 6.04,
        "总市值": 74112166000,
        "换手率": 2.97,
        "上涨家数": 12,
        "下跌家数": 1,
        "领涨股票": "申联生物",
        "领涨股票-涨跌幅": 20.0,
        "总成交额": 0.0,
        "净流入": 0.0,
    },
]

STANDARD_CONSTITUENT_COLUMNS = [
    "序号",
    "代码",
    "名称",
    "最新价",
    "涨跌幅",
    "涨跌额",
    "成交量",
    "成交额",
    "振幅",
    "最高",
    "最低",
    "今开",
    "昨收",
    "换手率",
    "量比",
    "流通股",
    "流通市值",
    "市盈率-动态",
    "市净率",
    "data_source",
    "updated_at",
]

STANDARD_EVENT_COLUMNS = [
    "股票代码",
    "股票简称",
    "关键词",
    "新闻标题",
    "新闻内容",
    "发布时间",
    "文章来源",
    "新闻链接",
    "来源类别",
    "匹配类型",
]

ROMAN_SUFFIX_PATTERN = re.compile(r"[ⅠⅡⅢⅣⅤ]+$")


@dataclass(frozen=True)
class AKShareQueryWindow:
    start_date: str
    end_date: str


def normalize_industry_name(name: str) -> str:
    normalized = "".join(str(name).split())
    return ROMAN_SUFFIX_PATTERN.sub("", normalized)


def parse_chinese_amount(value: object) -> float:
    if value is None or pd.isna(value):
        return 0.0
    text = str(value).strip()
    if not text or text == "--":
        return 0.0
    unit_scale = 1.0
    if text.endswith("万亿"):
        unit_scale = 1_0000_0000_0000.0
        text = text[:-2]
    elif text.endswith("亿"):
        unit_scale = 100_000_000.0
        text = text[:-1]
    elif text.endswith("万"):
        unit_scale = 10_000.0
        text = text[:-1]
    try:
        return float(text.replace(",", "")) * unit_scale
    except ValueError:
        return 0.0


class AKShareMarketDataAdapter:
    def __init__(self, lookback_days: int = 140) -> None:
        end_day = date.today()
        start_day = end_day - timedelta(days=lookback_days)
        self.window = AKShareQueryWindow(
            start_date=start_day.strftime("%Y%m%d"),
            end_date=end_day.strftime("%Y%m%d"),
        )
        self.project_root = Path(__file__).resolve().parents[2]
        self.constituent_cache_dir = self.project_root / "data" / "raw" / "industry_constituents_cache"
        self.constituent_cache_dir.mkdir(parents=True, exist_ok=True)
        self.event_cache_dir = self.project_root / "data" / "raw" / "stock_events_cache"
        self.event_cache_dir.mkdir(parents=True, exist_ok=True)
        self.industry_rankings_cache_path = (
            self.project_root / "data" / "raw" / "industry_rankings_latest.json"
        )
        self._ths_industry_name_map: Optional[pd.DataFrame] = None

    def _empty_constituent_frame(self) -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_CONSTITUENT_COLUMNS)

    def _cache_path_for_industry(self, industry_name: str) -> Path:
        safe_name = normalize_industry_name(industry_name) or "unknown"
        return self.constituent_cache_dir / f"{safe_name}.json"

    def _event_cache_path(self, symbol: str) -> Path:
        return self.event_cache_dir / f"{symbol}_{date.today().strftime('%Y%m%d')}.json"

    def _load_constituent_cache(self, industry_name: str, limit: Optional[int] = None) -> pd.DataFrame:
        cache_path = self._cache_path_for_industry(industry_name)
        if not cache_path.exists():
            return self._empty_constituent_frame()

        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        records = payload.get("items", [])
        if not records:
            return self._empty_constituent_frame()

        df = pd.DataFrame(records)
        for column in STANDARD_CONSTITUENT_COLUMNS:
            if column not in df.columns:
                df[column] = 0.0 if column not in {"代码", "名称", "data_source", "updated_at"} else ""
        if limit is not None:
            df = df.head(limit)
        return df.reset_index(drop=True)

    def _save_constituent_cache(self, industry_name: str, df: pd.DataFrame, source: str) -> None:
        cache_path = self._cache_path_for_industry(industry_name)
        payload = {
            "industry_name": industry_name,
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": df.to_dict(orient="records"),
        }
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _empty_event_frame(self) -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_EVENT_COLUMNS)

    def _load_event_cache(self, symbol: str) -> pd.DataFrame:
        cache_path = self._event_cache_path(symbol)
        if not cache_path.exists():
            return self._empty_event_frame()

        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        records = payload.get("items", [])
        if not records:
            return self._empty_event_frame()

        df = pd.DataFrame(records)
        for column in STANDARD_EVENT_COLUMNS:
            if column not in df.columns:
                df[column] = ""
        df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
        return df.dropna(subset=["发布时间"]).reset_index(drop=True)

    def _save_event_cache(self, symbol: str, stock_name: str, df: pd.DataFrame) -> None:
        payload = {
            "symbol": symbol,
            "stock_name": stock_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": df.to_dict(orient="records"),
        }
        self._event_cache_path(symbol).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _get_ths_industry_name_map(self) -> pd.DataFrame:
        if self._ths_industry_name_map is not None:
            return self._ths_industry_name_map

        df = run_without_proxy(stock_board_industry_name_ths, retries=3, retry_delay=1.0)
        df = df.copy()
        df["name"] = df["name"].astype(str)
        df["normalized_name"] = df["name"].map(normalize_industry_name)
        self._ths_industry_name_map = df
        return df

    def _load_industry_rankings_cache(self) -> pd.DataFrame:
        if not self.industry_rankings_cache_path.exists():
            return pd.DataFrame()
        payload = json.loads(self.industry_rankings_cache_path.read_text(encoding="utf-8"))
        return pd.DataFrame(payload.get("items", []))

    def _save_industry_rankings_cache(self, df: pd.DataFrame, source: str) -> None:
        payload = {
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": df.to_dict(orient="records"),
        }
        self.industry_rankings_cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def fetch_industry_rankings(self) -> pd.DataFrame:
        try:
            summary_df = run_without_proxy(stock_board_industry_summary_ths, retries=5, retry_delay=1.0)
            name_map_df = self._get_ths_industry_name_map()
            enriched_df = summary_df.copy()
            enriched_df.rename(
                columns={
                    "板块": "板块名称",
                    "领涨股": "领涨股票",
                    "领涨股-最新价": "领涨股票-最新价",
                    "领涨股-涨跌幅": "领涨股票-涨跌幅",
                },
                inplace=True,
            )
            enriched_df = enriched_df.merge(
                name_map_df[["name", "code"]],
                left_on="板块名称",
                right_on="name",
                how="left",
            )
            enriched_df.rename(columns={"code": "板块代码"}, inplace=True)
            enriched_df["板块代码"] = enriched_df["板块代码"].fillna("")
            numeric_columns = [
                "涨跌幅",
                "总成交量",
                "总成交额",
                "净流入",
                "上涨家数",
                "下跌家数",
                "均价",
                "领涨股票-最新价",
                "领涨股票-涨跌幅",
            ]
            for column in numeric_columns:
                enriched_df[column] = pd.to_numeric(enriched_df[column], errors="coerce")
            enriched_df["data_source"] = "ths_industry_summary"
            enriched_df = enriched_df.reset_index(drop=True)
            self._save_industry_rankings_cache(enriched_df, source="ths_industry_summary")
            return enriched_df
        except Exception:
            cached_df = self._load_industry_rankings_cache()
            if not cached_df.empty:
                return cached_df
            df = pd.DataFrame(FALLBACK_INDUSTRY_ROWS)
            numeric_columns = [
                "最新价",
                "涨跌额",
                "涨跌幅",
                "总市值",
                "换手率",
                "上涨家数",
                "下跌家数",
                "领涨股票-涨跌幅",
                "总成交额",
                "净流入",
            ]
            for column in numeric_columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
            df["data_source"] = "fallback_static"
            return df

    def _fetch_ths_industry_constituents(self, industry_name: str) -> pd.DataFrame:
        ths_name_map = self._get_ths_industry_name_map()
        normalized_name = normalize_industry_name(industry_name)

        exact_match = ths_name_map.loc[ths_name_map["name"] == industry_name]
        if exact_match.empty:
            exact_match = ths_name_map.loc[ths_name_map["normalized_name"] == normalized_name]
        if exact_match.empty:
            exact_match = ths_name_map.loc[
                ths_name_map["normalized_name"].str.contains(normalized_name, na=False)
            ]
        if exact_match.empty:
            raise KeyError(industry_name)

        symbol_code = str(exact_match.iloc[0]["code"])
        url = f"http://q.10jqka.com.cn/thshy/detail/code/{symbol_code}/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }

        def _fetch_table() -> pd.DataFrame:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            tables = pd.read_html(StringIO(response.text))
            if not tables:
                raise ValueError(f"No constituent table found for {industry_name}")
            return tables[0]

        df = run_without_proxy(_fetch_table, retries=4, retry_delay=1.0)
        df = df.copy()
        df.rename(
            columns={
                "现价": "最新价",
                "涨跌幅(%)": "涨跌幅",
                "涨跌": "涨跌额",
                "换手(%)": "换手率",
                "振幅(%)": "振幅",
                "市盈率": "市盈率-动态",
            },
            inplace=True,
        )
        df["代码"] = df["代码"].astype(str).str.zfill(6)
        numeric_columns = ["序号", "最新价", "涨跌幅", "涨跌额", "涨速(%)", "换手率", "量比", "振幅"]
        for column in numeric_columns:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
        for column in ["成交额", "流通股", "流通市值"]:
            if column in df.columns:
                df[column] = df[column].map(parse_chinese_amount)

        standardized = pd.DataFrame(
            {
                "序号": df.get("序号", pd.Series(dtype=float)),
                "代码": df.get("代码", pd.Series(dtype=str)),
                "名称": df.get("名称", pd.Series(dtype=str)),
                "最新价": df.get("最新价", pd.Series(dtype=float)),
                "涨跌幅": df.get("涨跌幅", pd.Series(dtype=float)),
                "涨跌额": df.get("涨跌额", pd.Series(dtype=float)),
                "成交量": 0.0,
                "成交额": df.get("成交额", pd.Series(dtype=float)),
                "振幅": df.get("振幅", pd.Series(dtype=float)),
                "最高": 0.0,
                "最低": 0.0,
                "今开": 0.0,
                "昨收": 0.0,
                "换手率": df.get("换手率", pd.Series(dtype=float)),
                "量比": df.get("量比", pd.Series(dtype=float)),
                "流通股": df.get("流通股", pd.Series(dtype=float)),
                "流通市值": df.get("流通市值", pd.Series(dtype=float)),
                "市盈率-动态": df.get("市盈率-动态", pd.Series(dtype=float)),
                "市净率": 0.0,
                "data_source": "ths_industry_constituents",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        for column in STANDARD_CONSTITUENT_COLUMNS:
            if column not in standardized.columns:
                standardized[column] = 0.0 if column not in {"代码", "名称", "data_source", "updated_at"} else ""
        return standardized[STANDARD_CONSTITUENT_COLUMNS].dropna(subset=["代码"]).reset_index(drop=True)

    def fetch_industry_constituents(
        self, industry_name: str, limit: Optional[int] = None
    ) -> pd.DataFrame:
        try:
            df = self._fetch_ths_industry_constituents(industry_name)
            self._save_constituent_cache(industry_name, df, source="ths_industry_constituents")
            if limit is not None:
                df = df.head(limit)
            return df.reset_index(drop=True)
        except Exception:
            try:
                df = run_without_proxy(ak.stock_board_industry_cons_em, symbol=industry_name)
                df = df.copy()
                for column in STANDARD_CONSTITUENT_COLUMNS:
                    if column not in df.columns:
                        df[column] = 0.0 if column not in {"代码", "名称", "data_source", "updated_at"} else ""
                df["代码"] = df["代码"].astype(str).str.zfill(6)
                df["data_source"] = "eastmoney_industry_constituents"
                df["updated_at"] = datetime.now(timezone.utc).isoformat()
                df = df[STANDARD_CONSTITUENT_COLUMNS].reset_index(drop=True)
                self._save_constituent_cache(
                    industry_name, df, source="eastmoney_industry_constituents"
                )
                if limit is not None:
                    df = df.head(limit)
                return df.reset_index(drop=True)
            except Exception:
                return self._load_constituent_cache(industry_name, limit=limit)

    def fetch_stock_daily_history(self, symbol: str) -> pd.DataFrame:
        try:
            sina_symbol = f"sh{symbol}" if symbol.startswith(("6", "9")) else f"sz{symbol}"
            df = run_without_proxy(
                ak.stock_zh_a_daily,
                symbol=sina_symbol,
                start_date=self.window.start_date,
                end_date=self.window.end_date,
                adjust="qfq",
                retries=2,
                retry_delay=0.8,
            )
            df = df.copy()
            df.rename(
                columns={
                    "date": "日期",
                    "open": "开盘",
                    "close": "收盘",
                    "high": "最高",
                    "low": "最低",
                    "volume": "成交量",
                    "amount": "成交额",
                    "turnover": "换手率",
                },
                inplace=True,
            )
            df["股票代码"] = symbol
            df["振幅"] = ((df["最高"] - df["最低"]) / df["收盘"].replace(0, pd.NA) * 100).fillna(0.0)
            df["涨跌额"] = df["收盘"].diff().fillna(0.0)
            df["涨跌幅"] = df["收盘"].pct_change().fillna(0.0) * 100
            df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce").fillna(0.0) * 100
            numeric_columns = [
                "开盘",
                "收盘",
                "最高",
                "最低",
                "成交量",
                "成交额",
                "振幅",
                "涨跌幅",
                "涨跌额",
                "换手率",
            ]
            for column in numeric_columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
            df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
            df = df[
                [
                    "日期",
                    "股票代码",
                    "开盘",
                    "收盘",
                    "最高",
                    "最低",
                    "成交量",
                    "成交额",
                    "振幅",
                    "涨跌幅",
                    "涨跌额",
                    "换手率",
                ]
            ]
            return df.dropna(subset=["日期", "收盘"]).reset_index(drop=True)
        except Exception:
            pass

        try:
            df = run_without_proxy(
                ak.stock_zh_a_hist,
                symbol=symbol,
                period="daily",
                start_date=self.window.start_date,
                end_date=self.window.end_date,
                adjust="qfq",
                timeout=15,
            )
        except Exception:
            return pd.DataFrame(
                columns=[
                    "日期",
                    "股票代码",
                    "开盘",
                    "收盘",
                    "最高",
                    "最低",
                    "成交量",
                    "成交额",
                    "振幅",
                    "涨跌幅",
                    "涨跌额",
                    "换手率",
                ]
            )
        df = df.copy()
        numeric_columns = [
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "振幅",
            "涨跌幅",
            "涨跌额",
            "换手率",
        ]
        for column in numeric_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        return df.dropna(subset=["日期", "收盘"]).reset_index(drop=True)

    def fetch_stock_news(self, symbol: str, stock_name: str, limit: int = 8) -> pd.DataFrame:
        try:
            df = run_without_proxy(ak.stock_news_em, symbol=symbol, retries=2, retry_delay=0.6)
        except Exception:
            return self._empty_event_frame()

        df = df.copy()
        if df.empty:
            return self._empty_event_frame()

        df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
        df["股票代码"] = symbol
        df["股票简称"] = stock_name
        df["关键词"] = symbol
        df["来源类别"] = "个股资讯"
        df["匹配类型"] = "exact_symbol"
        return (
            df[
                [
                    "股票代码",
                    "股票简称",
                    "关键词",
                    "新闻标题",
                    "新闻内容",
                    "发布时间",
                    "文章来源",
                    "新闻链接",
                    "来源类别",
                    "匹配类型",
                ]
            ]
            .dropna(subset=["发布时间"])
            .head(limit)
            .reset_index(drop=True)
        )

    def fetch_stock_news_by_keyword(self, keyword: str, stock_name: str, limit: int = 8) -> pd.DataFrame:
        try:
            timestamp = str(int(datetime.now().timestamp() * 1000))
            callback = f"jQuery3510_{timestamp}"
            url = "https://search-api-web.eastmoney.com/search/jsonp"
            inner_param = {
                "uid": "",
                "keyword": keyword,
                "type": ["cmsArticleWebOld"],
                "client": "web",
                "clientType": "web",
                "clientVersion": "curr",
                "param": {
                    "cmsArticleWebOld": {
                        "searchScope": "default",
                        "sort": "default",
                        "pageIndex": 1,
                        "pageSize": min(limit, 10),
                        "preTag": "<em>",
                        "postTag": "</em>",
                    }
                },
            }
            params = {
                "cb": callback,
                "param": json.dumps(inner_param, ensure_ascii=False),
                "_": timestamp,
            }
            headers = {
                "accept": "*/*",
                "accept-language": "zh-CN,zh;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "referer": f"https://so.eastmoney.com/news/s?keyword={keyword}",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            }
            response = curl_requests.get(
                url,
                params=params,
                headers=headers,
                timeout=8,
                impersonate="chrome124",
            )
            response.raise_for_status()
            data_text = response.text
            json_payload = data_text[data_text.find("(") + 1 : data_text.rfind(")")]
            data_json = json.loads(json_payload)
            df = pd.DataFrame(data_json["result"].get("cmsArticleWebOld", []))
        except Exception:
            return self._empty_event_frame()
        df = df.copy()
        if df.empty:
            return self._empty_event_frame()
        df["新闻链接"] = "http://finance.eastmoney.com/a/" + df["code"].astype(str) + ".html"
        df.rename(
            columns={
                "date": "发布时间",
                "mediaName": "文章来源",
                "title": "新闻标题",
                "content": "新闻内容",
            },
            inplace=True,
        )
        df["关键词"] = keyword
        df["股票代码"] = ""
        df["股票简称"] = stock_name
        df["来源类别"] = "关键词资讯"
        df["匹配类型"] = "name_keyword"
        df["新闻标题"] = (
            df["新闻标题"]
            .astype(str)
            .str.replace(r"\(<em>", "", regex=True)
            .str.replace(r"</em>\)", "", regex=True)
            .str.replace(r"<em>", "", regex=True)
            .str.replace(r"</em>", "", regex=True)
        )
        df["新闻内容"] = (
            df["新闻内容"]
            .astype(str)
            .str.replace(r"\(<em>", "", regex=True)
            .str.replace(r"</em>\)", "", regex=True)
            .str.replace(r"<em>", "", regex=True)
            .str.replace(r"</em>", "", regex=True)
            .str.replace(r"\u3000", "", regex=True)
            .str.replace(r"\r\n", " ", regex=True)
        )
        df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
        return (
            df[
                [
                    "股票代码",
                    "股票简称",
                    "关键词",
                    "新闻标题",
                    "新闻内容",
                    "发布时间",
                    "文章来源",
                    "新闻链接",
                    "来源类别",
                    "匹配类型",
                ]
            ]
            .dropna(subset=["发布时间"])
            .head(limit)
            .reset_index(drop=True)
        )

    def fetch_stock_research_reports(self, symbol: str, stock_name: str, limit: int = 4) -> pd.DataFrame:
        try:
            df = run_without_proxy(ak.stock_research_report_em, symbol=symbol, retries=2, retry_delay=0.8)
        except Exception:
            return self._empty_event_frame()

        df = df.copy()
        if df.empty:
            return self._empty_event_frame()

        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df["股票代码"] = symbol
        df["股票简称"] = stock_name
        df["关键词"] = symbol
        df["新闻标题"] = df["报告名称"].astype(str)
        df["新闻内容"] = (
            "机构："
            + df["机构"].astype(str)
            + "；评级："
            + df["东财评级"].astype(str)
            + "；行业："
            + df["行业"].astype(str)
        )
        df["发布时间"] = df["日期"]
        df["文章来源"] = "东方财富研报"
        df["新闻链接"] = df["报告PDF链接"].astype(str)
        df["来源类别"] = "券商研报"
        df["匹配类型"] = "exact_symbol"
        return (
            df[
                [
                    "股票代码",
                    "股票简称",
                    "关键词",
                    "新闻标题",
                    "新闻内容",
                    "发布时间",
                    "文章来源",
                    "新闻链接",
                    "来源类别",
                    "匹配类型",
                ]
            ]
            .dropna(subset=["发布时间"])
            .head(limit)
            .reset_index(drop=True)
        )

    def fetch_stock_disclosures(self, symbol: str, stock_name: str, limit: int = 6) -> pd.DataFrame:
        start_date = (date.today() - timedelta(days=21)).strftime("%Y%m%d")
        end_date = date.today().strftime("%Y%m%d")
        try:
            df = run_without_proxy(
                ak.stock_zh_a_disclosure_report_cninfo,
                symbol=symbol,
                market="沪深京",
                keyword="",
                category="",
                start_date=start_date,
                end_date=end_date,
                retries=2,
                retry_delay=0.8,
            )
        except Exception:
            return self._empty_event_frame()

        df = df.copy()
        if df.empty:
            return self._empty_event_frame()

        df["公告时间"] = pd.to_datetime(df["公告时间"], errors="coerce")
        df["股票代码"] = df["代码"].astype(str).str.zfill(6)
        df["股票简称"] = df["简称"].astype(str)
        df["关键词"] = symbol
        df["新闻标题"] = (
            df["公告标题"]
            .astype(str)
            .str.replace(r"<em>", "", regex=True)
            .str.replace(r"</em>", "", regex=True)
        )
        df["新闻内容"] = df["新闻标题"]
        df["发布时间"] = df["公告时间"]
        df["文章来源"] = "巨潮资讯"
        df["新闻链接"] = df["公告链接"].astype(str)
        df["来源类别"] = "官方公告"
        df["匹配类型"] = "exact_symbol"
        return (
            df[
                [
                    "股票代码",
                    "股票简称",
                    "关键词",
                    "新闻标题",
                    "新闻内容",
                    "发布时间",
                    "文章来源",
                    "新闻链接",
                    "来源类别",
                    "匹配类型",
                ]
            ]
            .dropna(subset=["发布时间"])
            .head(limit)
            .reset_index(drop=True)
        )

    def fetch_stock_event_feed(self, symbol: str, stock_name: str, limit: int = 12) -> pd.DataFrame:
        cached = self._load_event_cache(symbol)
        if not cached.empty:
            return cached.head(limit).reset_index(drop=True)

        frames = [
            self.fetch_stock_disclosures(symbol=symbol, stock_name=stock_name, limit=min(limit, 6)),
            self.fetch_stock_news(symbol=symbol, stock_name=stock_name, limit=min(limit, 6)),
            self.fetch_stock_research_reports(symbol=symbol, stock_name=stock_name, limit=min(limit, 4)),
        ]

        combined = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
        if combined.empty:
            fallback = self.fetch_stock_news_by_keyword(
                keyword=stock_name,
                stock_name=stock_name,
                limit=min(limit, 6),
            )
            if fallback.empty:
                return self._empty_event_frame()
            combined = fallback

        combined = combined.copy()
        combined["发布时间"] = pd.to_datetime(combined["发布时间"], errors="coerce")
        combined = combined.dropna(subset=["发布时间"])
        combined["去重键"] = (
            combined["来源类别"].astype(str)
            + "::"
            + combined["新闻标题"].astype(str)
            + "::"
            + combined["发布时间"].astype(str)
        )
        combined = combined.drop_duplicates(subset=["去重键"], keep="first").drop(columns=["去重键"])
        combined.sort_values("发布时间", ascending=False, inplace=True)
        combined = combined.head(limit).reset_index(drop=True)
        self._save_event_cache(symbol=symbol, stock_name=stock_name, df=combined)
        return combined

    def fetch_market_news(self, limit: int = 12) -> pd.DataFrame:
        try:
            df = run_without_proxy(ak.stock_info_global_em, retries=2, retry_delay=0.8)
        except Exception:
            return pd.DataFrame(columns=["标题", "摘要", "发布时间", "链接"])
        df = df.copy()
        df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
        return df.dropna(subset=["发布时间"]).head(limit).reset_index(drop=True)

    def fetch_code_name_map(self) -> pd.DataFrame:
        df = run_without_proxy(ak.stock_info_a_code_name, retries=4, retry_delay=1.0)
        df = df.copy()
        df["code"] = df["code"].astype(str).str.zfill(6)
        df["name"] = df["name"].astype(str)
        return df
