"""Search quality test battery — evaluates FTS search."""

import asyncio

import httpx

API = "http://localhost:8000"


async def search(client: httpx.AsyncClient, q: str, limit: int = 20) -> list[dict]:
    resp = await client.get("/v1/search", params={"q": q, "limit": limit})
    if resp.status_code != 200:
        return []
    return resp.json()


async def fetch_all_clients(client: httpx.AsyncClient) -> list[dict]:
    items: list[dict] = []
    cursor: str | None = None
    while True:
        params: dict[str, str | int] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        resp = await client.get("/v1/clients", params=params)
        page = resp.json()
        items.extend(page["items"])
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    return items


def pick_some(items: list[dict], field: str) -> str | None:
    for item in items:
        val = item.get(field)
        if val:
            return val
    return None


class Result:
    def __init__(self, name: str, query: str, expected: str, hits: list[dict], note: str = ""):
        self.name = name
        self.query = query
        self.expected = expected
        self.hits = hits
        self.note = note

    @property
    def pass_(self) -> bool:
        return len(self.hits) > 0

    @property
    def top_hit_email(self) -> str:
        return self.hits[0]["client"]["email"] if self.hits else "\u2014"

    @property
    def top_hit_name(self) -> str:
        if not self.hits:
            return "\u2014"
        c = self.hits[0]["client"]
        return f"{c['first_name']} {c['last_name']}"

    @property
    def top_score(self) -> float:
        return self.hits[0]["score"] if self.hits else 0.0


async def main():
    async with httpx.AsyncClient(base_url=API, timeout=10) as client:
        all_clients = await fetch_all_clients(client)
        total = len(all_clients)
        print(f"Total clients in DB: {total}\n")

        if total == 0:
            print("No clients in DB. Seed some data first, then re-run.")
            return

        results: list[Result] = []

        first = all_clients[0]
        fname = first["first_name"]
        lname = first["last_name"]
        full = f"{fname} {lname}"
        email = first["email"]
        domain = email.split("@")[1].split(".")[0]

        results.append(Result("Name: exact full", full, f"find {full}", await search(client, full)))
        results.append(
            Result("Name: first only", fname,
                   f"clients named {fname}",
                   await search(client, fname)))
        results.append(
            Result("Name: last only", lname,
                   f"clients named {lname}",
                   await search(client, lname)))
        results.append(
            Result("Name: lowercase", fname.lower(),
                   "case insensitive",
                   await search(client, fname.lower())))
        results.append(
            Result("Name: UPPERCASE", fname.upper(),
                   "case insensitive",
                   await search(client, fname.upper())))

        results.append(
            Result("Email: full", email,
                   f"find {email}",
                   await search(client, email)))
        results.append(
            Result("Email: domain", domain,
                   f"clients with @{domain}",
                   await search(client, domain)))

        desc = first.get("description") or ""
        if desc:
            word = desc.split()[0].strip(".,;:?!")
            results.append(
                Result("Description: single word", word,
                       "word from description",
                       await search(client, word)))

        social = first.get("social_links") or []
        if social:
            link = social[0]
            platform = link.split("//")[-1].split(".")[0]
            results.append(
                Result("Social: platform", platform,
                       "social link match",
                       await search(client, platform)))

        results.append(Result(
            "Ranking: name > desc", f"{fname} vs phrase",
            "name match scores higher", await search(client, fname),
            f"check top scores all have {fname} in name"))

        results.append(
            Result("Negative: gibberish", "xyzzyqwerty123",
                   "0 results",
                   await search(client, "xyzzyqwerty123")))
        results.append(
            Result("Negative: stopword", "the",
                   "likely 0 results",
                   await search(client, "the")))

        limited = await search(client, fname, limit=3)
        results.append(
            Result("Limit: max 3", f"{fname} limit=3",
                   "<=3 results", limited,
                   f"got {len(limited)}"))

        phrase_results = await search(client, '"retired executive"')
        results.append(
            Result("Phrase: quoted", '"retired executive"',
                   "phrase match", phrase_results))

        multi = await search(client, "retired london")
        results.append(Result("Multi-word: AND", "retired london", "AND of terms", multi))

        print_report(results, total)


def print_report(results: list[Result], total: int) -> None:
    print("=" * 90)
    print(f"  SEARCH QUALITY REPORT — {total} clients, {len(results)} test queries")
    print("=" * 90)

    passed = 0
    failed = 0
    for r in results:
        status = "PASS" if r.pass_ else "FAIL"
        if r.name.startswith("Negative") and not r.pass_:
            status = "PASS"
        if r.name.startswith("Limit") and len(r.hits) <= 3:
            status = "PASS"
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"\n[{status}] {r.name}")
        print(f"  query:    {r.query!r}")
        print(f"  expected: {r.expected}")
        print(f"  hits:     {len(r.hits)}")
        if r.hits:
            name = r.top_hit_name
            email = r.top_hit_email
            print(f"  top hit:  {name} <{email}>  score={r.top_score:.4f}")
            if len(r.hits) > 1:
                c2 = r.hits[1]["client"]
                print(
                    f"  2nd hit:  {c2['first_name']} {c2['last_name']}"
                    f"  score={r.hits[1]['score']:.4f}"
                )
        if r.note:
            print(f"  note:     {r.note}")

    print("\n" + "=" * 90)
    print(f"  SUMMARY: {passed} passed, {failed} failed out of {len(results)} tests")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
