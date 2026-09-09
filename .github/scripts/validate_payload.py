import json
import sys

EXPECTED = {"DE", "ES", "FR", "IT", "PL"} 


def _reject(value):
    raise ValueError(f"payload contains the non-JSON constant {value}")


def main(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle, parse_constant=_reject)

    if not payload.get("issued"):
        sys.exit("payload has no issued timestamp") 

    countries = payload.get("countries") or {}        
    if not countries:
        sys.exit("payload has no countries")

    unknown = sorted(set(countries) - EXPECTED)
    if unknown:
        sys.exit(f"unexpected countries {unknown}")

    for code, block in countries.items():
        if not block.get("forecast"):
            sys.exit(f"{code} has an empty forecast")
        if not block.get("recent"):
            sys.exit(f"{code} has no recent actuals")

    missing = sorted(EXPECTED - set(countries))
    suffix = f", missing {missing}" if missing else ""
    print(f"ok: issued {payload['issued']}, {len(countries)} countries{suffix}")


if __name__ == "__main__":
    main(sys.argv[1])