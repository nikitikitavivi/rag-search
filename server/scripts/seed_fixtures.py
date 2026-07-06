"""Generate 120 realistic WealthTech clients and insert them via the API."""

import asyncio
import random

import httpx

random.seed(42)

API = "http://localhost:8000"

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Dorothy", "George", "Melissa",
    "Edward", "Deborah", "Ronald", "Stephanie", "Timothy", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Shirley", "Eric", "Angela", "Jonathan", "Helen", "Stephen", "Anna",
    "Larry", "Brenda", "Justin", "Pamela", "Scott", "Nicole", "Brandon", "Emma",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Gregory", "Christine", "Frank", "Debra",
    "Alexander", "Rachel", "Raymond", "Catherine", "Patrick", "Carolyn", "Jack", "Janet",
    "Dennis", "Ruth", "Jerry", "Maria", "Tyler", "Heather", "Aaron", "Diane",
    "Henry", "Virginia", "Douglas", "Julie", "Peter", "Joyce", "Jose", "Victoria",
    "Adam", "Olivia", "Nathan", "Kelly", "Zachary", "Christina", "Walter", "Lauren",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen",
    "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera",
    "Campbell", "Mitchell", "Carter", "Roberts", "Goldman", "Stern", "Rothschild",
    "Vanderbilt", "Rockefeller", "Morgan", "Astor", "Carnegie", "Walton", "Buffett",
    "Soros", "Dalio", "Ackman", "Icahn", "Druckenmiller", "Berkshire", "Kennedy",
    "Bush", "Clinton", "Obama", "Trump", "Biden", "Reagan", "Carter", "Ford",
]

DOMAINS = [
    "neviswealth", "goldman", "morganstanley", "jpmorgan", "fidelity", "vanguard",
    "schwab", "merilllynch", "ubs", "creditssuisse", "barclays", "deutsche",
    "hsbc", "citigroup", "wellsfargo", "bridgewater", "renaissance", "citadel",
    "blackstone", "apollo", "kkr", "carlyle", "aqr", "two-sigma", "janus",
    "pimco", "blackrock", "statestreet", "northerntrust", "bnymellon",
]

CITIES = [
    "New York", "London", "Zurich", "Geneva", "Singapore", "Hong Kong",
    "Tokyo", "Frankfurt", "Paris", "Dubai", "Toronto", "Sydney",
    "San Francisco", "Los Angeles", "Chicago", "Boston", "Miami", "Dallas",
]

ROLES = [
    "Wealth management client", "Private banking client", "Family office principal",
    "Pension fund manager", "Hedge fund partner", "Retirement planning client",
    "Estate planning client", "Tax advisory client", "Trust beneficiary",
    "Investment advisor", "Portfolio manager", "Financial consultant",
    "Angel investor", "Venture capital partner", "Real estate investor",
    "Retired executive", "Business owner", "Corporate treasurer",
]

COMPANIES = [
    "NevisWealth", "Goldman Sachs", "Morgan Stanley", "JPMorgan Chase", "Fidelity",
    "Vanguard", "Charles Schwab", "Merrill Lynch", "UBS", "Credit Suisse",
    "Barclays", "Deutsche Bank", "HSBC", "Citigroup", "Wells Fargo",
    "Bridgewater Associates", "Renaissance Technologies", "Citadel", "Blackstone",
]

SOCIAL_PLATFORMS = ["linkedin", "instagram", "twitter", "facebook"]


def make_email(first: str, last: str, domain: str, idx: int) -> str:
    styles = [
        f"{first.lower()}.{last.lower()}@{domain}.com",
        f"{first.lower()}{last.lower()}@{domain}.com",
        f"{first[0].lower()}{last.lower()}@{domain}.com",
        f"{first.lower()}_{last.lower()}@{domain}.com",
        f"{last.lower()}.{first.lower()}@{domain}.com",
        f"{first.lower()}{idx}@{domain}.com",
    ]
    return random.choice(styles)


def make_description(role: str, company: str, city: str) -> str:
    templates = [
        f"{role} at {company}. Based in {city}.",
        f"{role} specializing in alternative investments. Previously at {company}.",
        f"High-net-worth individual. {role}. Located in {city}.",
        f"{role} with focus on sustainable and ESG investing. {company} alumni.",
        f"Multi-generational wealth planning. {role} in {city}. {company} client.",
        f"{role}. Interests include philanthropy, art collection, and real estate.",
        f"Retired {role}. Now managing family trust. {city} resident.",
        f"{role} at {company}. Chartered Financial Analyst (CFA). {city}.",
    ]
    return random.choice(templates)


def make_social_links(first: str, last: str) -> list[str]:
    links = []
    for platform in random.sample(SOCIAL_PLATFORMS, k=random.randint(1, 3)):
        links.append(f"https://{platform}.com/{first.lower()}{last.lower()}")
    return links


def generate_clients(n: int = 120) -> list[dict]:
    clients = []
    used_emails: set[str] = set()
    for i in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        domain = random.choice(DOMAINS)
        email = make_email(first, last, domain, i)
        while email in used_emails:
            email = make_email(first, last, domain, i + 1000)
        used_emails.add(email)

        role = random.choice(ROLES)
        company = random.choice(COMPANIES)
        city = random.choice(CITIES)

        clients.append({
            "first_name": first,
            "last_name": last,
            "email": email,
            "description": make_description(role, company, city),
            "social_links": make_social_links(first, last),
        })
    return clients


async def insert_clients(clients: list[dict]) -> tuple[int, int]:
    created = 0
    conflicts = 0
    async with httpx.AsyncClient(base_url=API, timeout=10) as client:
        for c in clients:
            resp = await client.post("/v1/clients", json=c)
            if resp.status_code == 201:
                created += 1
            elif resp.status_code == 409:
                conflicts += 1
            else:
                print(f"  WARN: {resp.status_code} for {c['email']}: {resp.text[:100]}")
    return created, conflicts


async def main():
    clients = generate_clients(120)
    print(f"Generated {len(clients)} fixture clients.")
    created, conflicts = await insert_clients(clients)
    print(f"Inserted: {created} created, {conflicts} conflicts.")
    return created


if __name__ == "__main__":
    asyncio.run(main())
