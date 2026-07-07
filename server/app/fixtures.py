import logging

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.client import Client
from app.schemas.client import ClientCreate
from app.services.clients import ClientService, DuplicateEmailError

logger = logging.getLogger(__name__)

SAMPLE_CLIENTS = [
    {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@neviswealth.com",
        "description": "Wealth management client at NevisWealth.",
        "social_links": ["https://linkedin.com/in/johndoe"],
    },
    {
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@example.com",
        "description": "Private banking client with a diversified portfolio.",
        "social_links": ["https://twitter.com/janesmith"],
    },
    {
        "first_name": "Robert",
        "last_name": "Johnson",
        "email": "robert.johnson@wealthcorp.com",
        "description": "Retirement planning client with interests in ESG investing.",
        "social_links": [],
    },
    {
        "first_name": "Emily",
        "last_name": "Chen",
        "email": "emily.chen@fintech.io",
        "description": "Tech entrepreneur exploring early-stage investment opportunities.",
        "social_links": ["https://linkedin.com/in/emilychen", "https://github.com/emilychen"],
    },
    {
        "first_name": "Michael",
        "last_name": "Brown",
        "email": "michael.brown@trustfund.org",
        "description": "Philanthropy-focused client managing a family trust.",
        "social_links": ["https://linkedin.com/in/michaelbrown"],
    },
]


async def run_fixtures() -> None:
    async with SessionLocal() as session:
        count_result = await session.execute(select(func.count()).select_from(Client))
        existing = count_result.scalar_one()
        if existing > 0:
            logger.info("Fixtures already seeded (%d clients), skipping.", existing)
            return

    logger.info("Seeding fixtures: %d clients...", len(SAMPLE_CLIENTS))
    created = 0
    for data in SAMPLE_CLIENTS:
        async with SessionLocal() as session:
            svc = ClientService(session)
            try:
                await svc.create(ClientCreate(**data))
                created += 1
            except DuplicateEmailError:
                logger.info("Skipping duplicate email: %s", data["email"])
    logger.info("Fixtures seeded: %d clients.", created)
