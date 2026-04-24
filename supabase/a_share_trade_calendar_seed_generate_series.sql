truncate table public.a_share_trade_calendar;

insert into public.a_share_trade_calendar (trade_date, source)
select d::date as trade_date, 'akshare' as source
from generate_series(date '2026-01-01', date '2026-12-31', interval '1 day') as g(d)
where extract(isodow from d) between 1 and 5
  and d::date not in (
    date '2026-01-01', date '2026-01-02',
    date '2026-02-16', date '2026-02-17', date '2026-02-18', date '2026-02-19', date '2026-02-20', date '2026-02-23',
    date '2026-04-06',
    date '2026-05-01', date '2026-05-04', date '2026-05-05',
    date '2026-06-19',
    date '2026-09-25',
    date '2026-10-01', date '2026-10-02', date '2026-10-05', date '2026-10-06', date '2026-10-07'
  )
on conflict (trade_date) do update
  set source = excluded.source;

select count(*) as trade_days, min(trade_date) as first_trade_date, max(trade_date) as last_trade_date
from public.a_share_trade_calendar;
