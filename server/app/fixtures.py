"""Seed the database with fixture data on Vercel cold start.

Mirrors scripts/seed_fixtures.py and scripts/seed_documents.py but uses internal
services rather than HTTP so it works inside the serverless function.
"""

import logging
import random

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.client import Client
from app.models.document import Document
from app.schemas.client import ClientCreate
from app.schemas.document import DocumentCreate
from app.services.clients import ClientService, DuplicateEmailError
from app.services.documents import DocumentService
from app.services.embeddings import get_embedding_service
from app.services.llm import get_llm_service

logger = logging.getLogger(__name__)

random.seed(42)

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


def _make_email(first: str, last: str, domain: str, idx: int) -> str:
    styles = [
        f"{first.lower()}.{last.lower()}@{domain}.com",
        f"{first.lower()}{last.lower()}@{domain}.com",
        f"{first[0].lower()}{last.lower()}@{domain}.com",
        f"{first.lower()}_{last.lower()}@{domain}.com",
        f"{last.lower()}.{first.lower()}@{domain}.com",
        f"{first.lower()}{idx}@{domain}.com",
    ]
    return random.choice(styles)


def _make_description(role: str, company: str, city: str) -> str:
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


def _make_social_links(first: str, last: str) -> list[str]:
    links = []
    for platform in random.sample(SOCIAL_PLATFORMS, k=random.randint(1, 3)):
        links.append(f"https://{platform}.com/{first.lower()}{last.lower()}")
    return links


def _generate_clients(n: int = 120) -> list[dict]:
    clients = []
    used_emails: set[str] = set()
    for i in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        domain = random.choice(DOMAINS)
        email = _make_email(first, last, domain, i)
        while email in used_emails:
            email = _make_email(first, last, domain, i + 1000)
        used_emails.add(email)

        role = random.choice(ROLES)
        company = random.choice(COMPANIES)
        city = random.choice(CITIES)

        clients.append({
            "first_name": first,
            "last_name": last,
            "email": email,
            "description": _make_description(role, company, city),
            "social_links": _make_social_links(first, last),
        })
    return clients


async def run_fixtures() -> None:
    await _seed_clients()
    await _seed_documents()


async def _seed_clients() -> None:
    async with SessionLocal() as session:
        count_result = await session.execute(select(func.count()).select_from(Client))
        existing = count_result.scalar_one()
        if existing > 0:
            logger.info("Client fixtures already seeded (%d), skipping.", existing)
            return

    clients = _generate_clients(120)
    logger.info("Seeding client fixtures: %d clients...", len(clients))
    created = 0
    conflicts = 0
    for data in clients:
        async with SessionLocal() as session:
            svc = ClientService(session)
            try:
                await svc.create(ClientCreate(**data))
                created += 1
            except DuplicateEmailError:
                conflicts += 1
    logger.info("Client fixtures seeded: %d created, %d conflicts.", created, conflicts)


_SEED_DOCS = [
    {
        "title": "Endocrine Disorder Management Protocol",
        "content": (
            "ENDOCRINE DISORDER MANAGEMENT PROTOCOL\n\n"
            "Clinical Overview\n"
            "This protocol establishes standardized procedures for managing chronic "
            "metabolic conditions characterized by impaired insulin production and "
            "glucose regulation. The endocrine system's role in maintaining homeostasis "
            "requires careful monitoring of pancreatic function and cellular response "
            "to hormonal signals. Patients presenting with elevated fasting blood "
            "glucose levels above 126 mg/dL require immediate intervention according "
            "to the American Association of Clinical Endocrinologists guidelines.\n\n"
            "Diagnostic Criteria\n"
            "The diagnostic pathway begins with glycated hemoglobin measurements, "
            "which provide a three-month average of blood sugar levels. Values above "
            "6.5% on two separate occasions confirm the diagnosis. The oral glucose "
            "tolerance test remains the gold standard for detecting impaired glucose "
            "tolerance, where patients ingest 75 grams of glucose and blood levels "
            "are measured at two-hour intervals. Fasting plasma glucose testing should "
            "be conducted after an eight-hour fast for accurate baseline readings.\n\n"
            "Pharmacological Interventions\n"
            "First-line treatment typically begins with metformin hydrochloride, which "
            "reduces hepatic glucose production and improves peripheral insulin "
            "sensitivity. The standard titration schedule starts at 500mg daily and "
            "increases to a maximum of 2000mg over several weeks to minimize "
            "gastrointestinal side effects. For patients who do not achieve target "
            "HbA1c levels with monotherapy, sulfonylureas such as glimepiride "
            "stimulate pancreatic beta cells to increase endogenous insulin secretion.\n\n"
            "Advanced therapeutic options include GLP-1 receptor agonists like "
            "semaglutide and liraglutide, which slow gastric emptying and promote "
            "satiety while enhancing glucose-dependent insulin release. SGLT2 "
            "inhibitors represent a newer class that promotes urinary glucose excretion "
            "and has demonstrated cardiovascular and renal protective benefits in "
            "multiple randomized controlled trials. DPP-4 inhibitors such as "
            "sitagliptin provide modest HbA1c reduction with a favorable side effect "
            "profile.\n\n"
            "Lifestyle Modification Requirements\n"
            "Medical nutrition therapy requires patients to work with registered "
            "dietitians to develop individualized meal plans focusing on carbohydrate "
            "counting and glycemic index awareness. The recommended macronutrient "
            "distribution includes 45-60% of calories from carbohydrates, 15-20% "
            "from protein, and 20-35% from fats, with saturated fat limited to less "
            "than 7% of total calories. Physical activity prescriptions should target "
            "a minimum of 150 minutes per week of moderate-intensity aerobic exercise "
            "combined with resistance training twice weekly.\n\n"
            "Monitoring and Follow-Up\n"
            "Quarterly HbA1c testing is recommended for patients not meeting treatment "
            "goals, while those with stable control may be tested semiannually. "
            "Self-monitoring of blood glucose should be performed at varying "
            "frequencies depending on the treatment regimen, with patients on "
            "intensive insulin therapy checking four to seven times daily. Annual "
            "comprehensive foot examinations, dilated eye examinations, and urine "
            "microalbumin testing are essential components of preventive care.\n\n"
            "Complication Surveillance\n"
            "Long-term metabolic dysregulation can lead to microvascular complications "
            "including retinopathy, nephropathy, and peripheral neuropathy. "
            "Macrovascular complications such as coronary artery disease, "
            "cerebrovascular disease, and peripheral arterial disease require "
            "aggressive risk factor modification. The UK Prospective Diabetes Study "
            "demonstrated that each 1% reduction in HbA1c correlates with a 37% "
            "decrease in microvascular complications and a 21% reduction in "
            "diabetes-related mortality.\n\n"
            "Patient Education Framework\n"
            "Structured education programs should cover hypoglycemia recognition and "
            "management, sick day rules, proper foot care techniques, and the "
            "importance of medication adherence. Carbohydrate counting education "
            "enables patients to match prandial insulin doses to meal content, "
            "improving postprandial glucose excursions. Psychosocial assessment "
            "should screen for diabetes distress, which affects approximately 36% "
            "of patients and negatively impacts self-management behaviors.\n\n"
            "Technology Integration\n"
            "Continuous glucose monitoring systems provide real-time interstitial "
            "glucose readings every five minutes, allowing patients and providers "
            "to identify glycemic patterns and trends. Insulin pump therapy, "
            "including hybrid closed-loop systems, automates basal insulin delivery "
            "and can reduce HbA1c by an additional 0.5-1.0% compared to multiple "
            "daily injections. Telemedicine platforms facilitate remote monitoring "
            "and medication adjustments, particularly beneficial for patients in "
            "rural or underserved areas.\n\n"
            "Population Health Considerations\n"
            "Disparities in outcomes persist across socioeconomic and racial groups, "
            "necessitating culturally tailored interventions. Community health worker "
            "programs have demonstrated effectiveness in improving glycemic control "
            "among underserved populations. Insurance coverage for diabetes "
            "self-management education and medical nutrition therapy varies "
            "significantly by state and payer type, creating barriers to "
            "comprehensive care delivery."
        ),
    },
    {
        "title": "Intangible Asset Protection Framework",
        "content": (
            "INTANGIBLE ASSET PROTECTION FRAMEWORK\n\n"
            "Introduction\n"
            "This document outlines the comprehensive legal framework for protecting "
            "creations of the mind, including inventions, literary and artistic works, "
            "designs, symbols, names, and images used in commerce. The modern knowledge "
            "economy depends on robust legal mechanisms that grant creators exclusive "
            "rights over their intangible assets for limited periods, balancing "
            "innovation incentives with public access to knowledge.\n\n"
            "Patent Law Fundamentals\n"
            "Patent protection grants inventors the right to exclude others from "
            "making, using, selling, or importing their invention for a period of "
            "twenty years from the filing date. To qualify for patentability, an "
            "invention must demonstrate novelty, non-obviousness to a person skilled "
            "in the relevant art, and practical utility. The specification must enable "
            "a person of ordinary skill to make and use the invention without undue "
            "experimentation, while claims define the precise legal boundaries of the "
            "protected subject matter.\n\n"
            "The America Invents Act of 2011 transitioned the United States from a "
            "first-to-invent to a first-inventor-to-file system, harmonizing with "
            "international norms. Provisional applications provide a twelve-month "
            "window to assess commercial viability before filing a non-provisional "
            "application, establishing an early priority date at lower cost. Patent "
            "Cooperation Treaty filings streamline international protection by "
            "allowing a single application to serve as a placeholder in over 150 "
            "member countries.\n\n"
            "Copyright Protection Scope\n"
            "Copyright subsists in original works of authorship fixed in any tangible "
            "medium of expression, including literary works, musical compositions, "
            "dramatic works, choreography, pictorial and graphic works, motion "
            "pictures, sound recordings, and architectural works. Protection attaches "
            "automatically upon fixation without requiring registration, though "
            "registration with the Copyright Office provides significant procedural "
            "advantages including the ability to seek statutory damages and "
            "attorney's fees in infringement actions.\n\n"
            "The duration of copyright protection for works created after January 1, "
            "1978 extends for the life of the author plus seventy years. For works "
            "made for hire, anonymous works, and pseudonymous works, protection lasts "
            "for ninety-five years from publication or 120 years from creation, "
            "whichever expires first. The fair use doctrine permits limited use of "
            "copyrighted material without permission for purposes such as criticism, "
            "comment, news reporting, teaching, scholarship, and research, evaluated "
            "through a four-factor balancing test.\n\n"
            "Trademark and Trade Dress\n"
            "Trademark law protects words, phrases, symbols, designs, or combinations "
            "thereof that identify and distinguish the source of goods or services. "
            "Rights arise through actual use in commerce, though federal registration "
            "on the Principal Register provides constructive nationwide notice, prima "
            "facie evidence of validity, and the potential for incontestability after "
            "five years of continuous use. The Lanham Act prohibits registration of "
            "marks that are merely descriptive, generic, deceptive, or likely to "
            "cause confusion with existing marks.\n\n"
            "Trade dress protection extends to the overall visual appearance and "
            "packaging of a product that serves as a source identifier. To establish "
            "infringement under Section 43(a) of the Lanham Act, plaintiffs must "
            "demonstrate that the trade dress is non-functional, inherently "
            "distinctive or has acquired secondary meaning, and that the defendant's "
            "use creates a likelihood of confusion among reasonable consumers.\n\n"
            "Trade Secret Protection\n"
            "Trade secret law protects confidential business information that derives "
            "independent economic value from not being generally known and is subject "
            "to reasonable efforts to maintain its secrecy. The Defend Trade Secrets "
            "Act of 2016 created a federal civil cause of action for trade secret "
            "misappropriation, supplementing the existing patchwork of state laws "
            "largely based on the Uniform Trade Secrets Act. Remedies include "
            "injunctive relief, damages for actual loss and unjust enrichment, "
            "exemplary damages for willful misappropriation, and attorney's fees in "
            "cases of bad faith.\n\n"
            "Reasonable secrecy measures may include non-disclosure agreements, "
            "access controls, encryption, employee training programs, and physical "
            "security protocols. The inevitable disclosure doctrine, recognized in "
            "some jurisdictions, permits courts to enjoin a former employee from "
            "working for a competitor where the employee's new position would "
            "inevitably result in disclosure of trade secrets, even absent evidence "
            "of actual misappropriation.\n\n"
            "International Harmonization\n"
            "The Agreement on Trade-Related Aspects of Intellectual Property Rights "
            "establishes minimum standards for IP protection among World Trade "
            "Organization members. The Madrid Protocol simplifies international "
            "trademark registration through a centralized filing system administered "
            "by the World Intellectual Property Organization. The Berne Convention "
            "for the Protection of Literary and Artistic Works mandates automatic "
            "copyright protection without formalities and establishes the principle "
            "of national treatment.\n\n"
            "Enforcement Mechanisms\n"
            "Rights holders may pursue remedies through federal district courts, the "
            "International Trade Commission for import-related infringement, and "
            "alternative dispute resolution including arbitration and mediation. "
            "Cease and desist letters serve as a preliminary enforcement tool, often "
            "resolving disputes without litigation. Digital Millennium Copyright Act "
            "takedown notices provide an administrative mechanism for removing "
            "infringing content from online platforms, though counter-notification "
            "procedures protect against abusive claims."
        ),
    },
    {
        "title": "Real Property Assessment Methodology",
        "content": (
            "REAL PROPERTY ASSESSMENT METHODOLOGY\n\n"
            "Fundamental Principles\n"
            "Property valuation represents the systematic process of estimating the "
            "market worth of land and improvements at a specific point in time. The "
            "concept of highest and best use underpins all valuation approaches, "
            "requiring the appraiser to determine the legally permissible, physically "
            "possible, financially feasible, and maximally productive use of the "
            "subject property. Market value assumes a willing buyer and seller, both "
            "acting with reasonable knowledge and without undue pressure, in an "
            "arms-length transaction conducted with typical marketing exposure.\n\n"
            "The principle of substitution states that a rational purchaser will pay "
            "no more for a property than the cost of acquiring an equally desirable "
            "substitute. Conformity suggests that maximum value is achieved when "
            "properties within a neighborhood maintain reasonable similarity in use, "
            "size, and quality. The principle of anticipation recognizes that value "
            "is created by the expectation of future benefits, whether through "
            "income generation, appreciation, or utility.\n\n"
            "Sales Comparison Approach\n"
            "The sales comparison approach derives value by analyzing recent "
            "transactions of comparable properties and adjusting for differences in "
            "physical characteristics, location, transaction conditions, and market "
            "conditions at the time of sale. Adjustments are applied to the "
            "comparable sales, not the subject property, and may be expressed as "
            "dollar amounts or percentages. An appraiser typically selects three to "
            "five comparable sales that required the fewest adjustments, as excessive "
            "adjustments reduce the reliability of the analysis.\n\n"
            "Location adjustments account for differences in neighborhood quality, "
            "proximity to amenities, school district boundaries, traffic patterns, "
            "and environmental factors such as flood zones or airport noise contours. "
            "Physical adjustments address variations in gross living area, lot size, "
            "bedroom and bathroom count, quality of construction, condition, "
            "functional utility, and presence of features such as fireplaces, pools, "
            "or views. Market conditions adjustments reflect changes in price levels "
            "between the comparable sale date and the effective valuation date.\n\n"
            "Income Capitalization Approach\n"
            "The income approach converts anticipated future income streams into a "
            "present value estimate, reflecting the investment decision-making "
            "process of market participants. Direct capitalization applies an overall "
            "capitalization rate derived from market data to a single year's "
            "stabilized net operating income. The capitalization rate represents the "
            "relationship between income and value and is extracted from comparable "
            "sales by dividing the property's net operating income by its sale price.\n\n"
            "Discounted cash flow analysis projects income and expenses over a "
            "multi-year holding period, applying a terminal capitalization rate to "
            "the final year's income to estimate reversion value. Cash flows and the "
            "reversion are discounted to present value using a discount rate that "
            "reflects the investor's required rate of return given the risk profile "
            "of the investment. Lease-by-lease analysis models each tenant's "
            "contractual rent, expense reimbursements, renewal probability, and "
            "downtime between tenancies for multi-tenant commercial properties.\n\n"
            "Cost Approach\n"
            "The cost approach estimates value as the land value plus the depreciated "
            "cost of improvements. Land value is typically derived through the sales "
            "comparison approach applied to vacant land parcels. Replacement cost new "
            "represents the expenditure required to construct a substitute improvement "
            "of equivalent utility using modern materials and methods, while "
            "reproduction cost new estimates the cost of constructing an exact "
            "replica.\n\n"
            "Depreciation is categorized into three forms: physical deterioration "
            "resulting from wear and tear and deferred maintenance, functional "
            "obsolescence caused by design deficiencies or super-adequacies relative "
            "to market standards, and external obsolescence arising from factors "
            "outside the property boundaries such as neighborhood decline or changes "
            "in zoning regulations. Accrued depreciation is measured through the "
            "age-life method, the breakdown method, or market extraction from "
            "comparable sales data.\n\n"
            "Special Purpose Properties\n"
            "Valuation of special purpose properties such as hospitals, schools, "
            "churches, and government buildings presents unique challenges due to "
            "limited market transaction data. These properties are typically valued "
            "using the cost approach as the primary method, supplemented by the "
            "income approach where the property generates revenue. Going concern "
            "value, which includes both real property and business enterprise value, "
            "must be distinguished from real property value for ad valorem taxation "
            "purposes.\n\n"
            "Mass Appraisal Systems\n"
            "Computer-assisted mass appraisal systems employ statistical modeling to "
            "value large portfolios of properties efficiently for property tax "
            "assessment purposes. Multiple regression analysis identifies the "
            "contribution of individual property characteristics to overall value, "
            "generating valuation equations applied uniformly across the assessment "
            "jurisdiction. Geographic information systems enable spatial analysis of "
            "value patterns and market trends, supporting ratio studies that evaluate "
            "assessment uniformity and equity.\n\n"
            "Regulatory Framework\n"
            "The Uniform Standards of Professional Appraisal Practice establish "
            "ethical and performance standards for appraisers in the United States. "
            "Financial Institutions Reform, Recovery, and Enforcement Act of 1989 "
            "mandates state licensing and certification of appraisers performing "
            "valuations for federally related transactions. International Valuation "
            "Standards promote consistency in valuation practice across national "
            "boundaries, facilitating cross-border investment and financial reporting."
        ),
    },
    {
        "title": "Distributed Computing Infrastructure Design",
        "content": (
            "DISTRIBUTED COMPUTING INFRASTRUCTURE DESIGN\n\n"
            "Architectural Overview\n"
            "Modern distributed computing environments leverage virtualized resource "
            "pools delivered over public networks as metered services, enabling "
            "organizations to replace upfront capital expenditure with variable "
            "operational expenditure. The shared responsibility model delineates "
            "security obligations between the service provider, responsible for "
            "security of the infrastructure, and the customer, responsible for "
            "security within the infrastructure including data classification, "
            "identity management, and application-level controls.\n\n"
            "Infrastructure as a Service provides virtualized compute, storage, and "
            "networking resources that customers provision and manage through "
            "self-service portals and programmatic interfaces. Platform as a Service "
            "abstracts the underlying infrastructure, providing managed runtime "
            "environments for application deployment without requiring customers to "
            "manage operating systems or middleware. Software as a Service delivers "
            "fully managed applications accessible through web browsers or APIs, "
            "eliminating customer responsibility for any infrastructure management.\n\n"
            "Compute Virtualization and Containerization\n"
            "Hypervisor technology enables multiple virtual machines to share "
            "physical host resources through hardware-assisted virtualization "
            "extensions found in modern processors. Type 1 hypervisors run directly "
            "on hardware without an intervening operating system, providing superior "
            "performance isolation compared to Type 2 hypervisors that operate as "
            "applications within a host operating system. Live migration capabilities "
            "allow running virtual machines to be transferred between physical hosts "
            "without service interruption, facilitating maintenance and load "
            "balancing.\n\n"
            "Containerization represents an operating-system-level virtualization "
            "approach that packages applications with their dependencies into "
            "isolated user-space instances sharing the host kernel. Unlike virtual "
            "machines, containers do not require a full guest operating system, "
            "resulting in significantly lower overhead and faster startup times "
            "measured in seconds rather than minutes. Orchestration platforms "
            "automate container deployment, scaling, and management across clusters "
            "of hosts, handling service discovery, load distribution, health "
            "monitoring, and rolling updates.\n\n"
            "Storage Architectures\n"
            "Object storage provides highly scalable, eventually consistent storage "
            "for unstructured data accessed through RESTful APIs, with each object "
            "containing data, metadata, and a unique identifier. Unlike traditional "
            "file systems, object storage employs a flat namespace rather than "
            "hierarchical directory structures, enabling horizontal scaling across "
            "distributed nodes. Block storage presents raw storage volumes that can "
            "be attached to virtual machines as persistent disks, supporting random "
            "read-write access patterns required by databases and transactional "
            "workloads.\n\n"
            "Content delivery networks cache static and dynamic content at edge "
            "locations geographically distributed near end users, reducing latency "
            "and origin server load. Replication strategies including synchronous "
            "and asynchronous mirroring ensure data durability and availability "
            "across multiple availability zones within a geographic region. Storage "
            "tiering policies automatically transition data between "
            "performance-optimized and cost-optimized storage classes based on "
            "access patterns and lifecycle rules.\n\n"
            "Networking and Security\n"
            "Virtual private networks establish encrypted tunnels between on-premises "
            "data centers and virtualized environments, enabling hybrid architectures "
            "that span private and public infrastructure. Software-defined networking "
            "decouples the control plane from the data plane, allowing network "
            "topology and policies to be managed programmatically through APIs "
            "rather than individual device configuration. Security groups and network "
            "access control lists provide stateful and stateless packet filtering at "
            "the instance and subnet boundaries respectively.\n\n"
            "Identity and access management systems enforce the principle of least "
            "privilege through role-based access controls, with temporary credentials "
            "generated through token services reducing the risk of long-lived "
            "credential compromise. Encryption protects data at rest using "
            "server-side mechanisms with provider-managed or customer-managed keys, "
            "and data in transit using Transport Layer Security protocols. API "
            "gateway services provide a single entry point for client requests, "
            "handling authentication, rate limiting, request transformation, and "
            "response caching.\n\n"
            "Scalability and Resilience\n"
            "Horizontal scaling adds additional compute instances behind load "
            "balancers that distribute incoming traffic based on configurable "
            "algorithms including round-robin, least connections, and weighted "
            "distribution. Auto-scaling policies dynamically adjust instance counts "
            "based on observed metrics such as CPU utilization, request latency, or "
            "custom application metrics published through monitoring services. "
            "Stateless application design, where session data is externalized to "
            "distributed caches or databases, enables any instance to serve any "
            "request without affinity requirements.\n\n"
            "Multi-region architectures replicate application stacks across "
            "geographically separated facilities to survive regional failures, with "
            "global load balancing routing users to the nearest healthy region. "
            "Chaos engineering practices deliberately inject failures into production "
            "systems to validate resilience assumptions and identify unexpected "
            "failure modes before they manifest during actual incidents. Circuit "
            "breaker patterns prevent cascading failures by detecting unresponsive "
            "downstream services and failing fast rather than accumulating queued "
            "requests.\n\n"
            "Observability and Operations\n"
            "Distributed tracing follows requests across service boundaries by "
            "propagating correlation identifiers, enabling latency analysis and "
            "bottleneck identification in microservice architectures. Centralized "
            "logging aggregates structured log events from all components into "
            "searchable indexes with retention policies balancing operational needs "
            "against storage costs. Metrics collection at one-minute granularity "
            "feeds dashboards and alerting systems that notify operators of threshold "
            "violations through multiple notification channels including email, "
            "messaging platforms, and automated incident response integrations."
        ),
    },
    {
        "title": "Residential Verification Statement",
        "content": (
            "This monthly service statement confirms the registered location of "
            "the account holder. The document includes the name of the subscriber, "
            "the premises where service is delivered, and the period of consumption "
            "covered by this statement. It serves as official confirmation of the "
            "connection between an individual and a fixed geographic location. "
            "Issuing authority is the local regulated provider of essential "
            "household services including electricity supply and water distribution. "
            "Statement identifier and meter reference numbers are printed on the "
            "upper section of each page."
        ),
    },
]

_TEST_CLIENT_EMAIL = "test@metadata.com"


async def _seed_documents() -> None:
    async with SessionLocal() as session:
        count_result = await session.execute(select(func.count()).select_from(Document))
        existing = count_result.scalar_one()
        if existing > 0:
            logger.info("Document fixtures already seeded (%d), skipping.", existing)
            return

    async with SessionLocal() as session:
        svc = ClientService(session)
        owner = await svc.get_by_email(_TEST_CLIENT_EMAIL)
        if owner is None:
            owner = await svc.create(ClientCreate(
                first_name="Test",
                last_name="User",
                email=_TEST_CLIENT_EMAIL,
                description="Test client for seeded documents",
            ))
            logger.info("Created test client: %s", owner.id)
        else:
            logger.info("Using existing test client: %s", owner.id)
        owner_id = owner.id

    emb = get_embedding_service()
    llm = get_llm_service()
    logger.info(
        "Seeding document fixtures: %d documents (embeddings=%s)...",
        len(_SEED_DOCS),
        "available" if emb.is_available else "unavailable",
    )

    created = 0
    for doc in _SEED_DOCS:
        async with SessionLocal() as session:
            svc = DocumentService(session, emb, llm)
            await svc.create(
                owner_id, DocumentCreate(title=doc["title"], content=doc["content"])
            )
            created += 1
            logger.info("  Created: %s", doc["title"])
    logger.info("Document fixtures seeded: %d created.", created)
