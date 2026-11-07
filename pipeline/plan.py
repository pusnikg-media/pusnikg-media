"""Pusnik G content plan helper (0 credits): print the pre-produced entry for a post date and prepare the work folder.
Usage: python3 pipeline/plan.py YYYY-MM-DD [workdir]
- prints the entry from plan/countdown_plan.json (or NO_PLAN_ENTRY if there is none)
- with workdir: writes workdir/script.txt (one line per sentence) and workdir/job_base.json
  (day, hook_big/hook_mid/hook_sub/badge, card, punch, vo_dir="vo", out) - the producer only adds shots + music.
The plan is a BASIS: big official GTA 6 news of the day and the Playbook rules (analyst) override it."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "..", "plan", "countdown_plan.json")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    date = sys.argv[1]
    plan = json.load(open(PLAN))
    e = next((x for x in plan["entries"] if x["date"] == date), None)
    if not e:
        print("NO_PLAN_ENTRY", date)
        return
    print(json.dumps(e, ensure_ascii=False, indent=1))
    if len(sys.argv) > 2:
        wd = sys.argv[2]; os.makedirs(wd, exist_ok=True)
        open(os.path.join(wd, "script.txt"), "w").write("\n".join(e["script"]) + "\n")
        day = e["day"]
        job = {"vo_dir": "vo", "day": day if day > 0 else 0, "hook_sub": e.get("hook_sub", ""),
               "card": e["card"], "punch": e.get("punch", []), "out": f"pusnikg-{date}.mp4"}
        for k in ("hook_big", "hook_mid", "badge"):
            if k in e:
                job[k] = e[k]
        json.dump(job, open(os.path.join(wd, "job_base.json"), "w"), indent=1, ensure_ascii=False)
        print(f"PLAN_READY {wd}/script.txt {wd}/job_base.json (add shots + music)")


if __name__ == "__main__":
    main()
