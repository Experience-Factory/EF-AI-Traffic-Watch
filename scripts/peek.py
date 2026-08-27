import datetime as dt, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import window as W, series as S
win = W.build(dt.date(2026, 8, 24))
bl = S.buckets(win)
rows = S.read("sessions_daily.csv")
fields = ["ai_sessions", "all_sessions", "ai_purchaseRevenue", "all_purchaseRevenue",
          "ai_transactions", "all_transactions", "ai_keyEvents", "ai_engagedSessions"]
idx = S.weekly(rows, ["venue"], None, fields, win["weeks"])
for venue in ("antwerp", "eupen"):
    S.fill(bl, idx, (venue,), fields)
print(f"{'bucket':<12}{'AI ANT':>8}{'share':>8}{'€AI':>8}{'€tot':>10}{'AI EUP':>8}{'share':>8}{'€AI':>7}{'€tot':>10}")
for b in bl:
    a = b["data"][("antwerp",)]; e = b["data"][("eupen",)]
    sh = lambda d: (d["ai_sessions"]/d["all_sessions"]*100) if d["all_sessions"] else 0
    print(f"{b['label']+' '+b['sub'][:6]:<12}{a['ai_sessions']:>8.0f}{sh(a):>7.2f}%{a['ai_purchaseRevenue']:>8.0f}{a['all_purchaseRevenue']:>10.0f}"
          f"{e['ai_sessions']:>8.0f}{sh(e):>7.2f}%{e['ai_purchaseRevenue']:>7.0f}{e['all_purchaseRevenue']:>10.0f}")
