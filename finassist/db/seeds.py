from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Category


# (parent_name, [(child, is_transfer, is_income), ...])
DEFAULT_CATEGORIES: list[tuple[str, int, int, list[tuple[str, int, int]]]] = [
    (
        "Income",
        0,
        1,
        [
            ("Salary", 0, 1),
            ("Interest", 0, 1),
            ("Dividends", 0, 1),
            ("Capital Gains", 0, 1),
            ("Refunds", 0, 1),
            ("Other Income", 0, 1),
        ],
    ),
    (
        "Housing",
        0,
        0,
        [
            ("Rent", 0, 0),
            ("Maintenance/Society", 0, 0),
            ("Utilities-Electricity", 0, 0),
            ("Utilities-Water", 0, 0),
            ("Utilities-Gas", 0, 0),
            ("Utilities-Internet", 0, 0),
            ("Repairs", 0, 0),
        ],
    ),
    (
        "Food",
        0,
        0,
        [
            ("Groceries", 0, 0),
            ("Eating Out", 0, 0),
            ("Food Delivery", 0, 0),
            ("Beverages/Cafe", 0, 0),
        ],
    ),
    (
        "Transport",
        0,
        0,
        [
            ("Fuel", 0, 0),
            ("Cab/Auto", 0, 0),
            ("Public Transit", 0, 0),
            ("Vehicle Maintenance", 0, 0),
            ("Parking/Toll", 0, 0),
            ("Travel-Long Distance", 0, 0),
        ],
    ),
    (
        "Health",
        0,
        0,
        [
            ("Doctor/Consultation", 0, 0),
            ("Pharmacy", 0, 0),
            ("Diagnostics", 0, 0),
            ("Insurance Premium-Health", 0, 0),
            ("Fitness/Gym", 0, 0),
        ],
    ),
    (
        "Family",
        0,
        0,
        [
            ("Pocket Money - Mom", 0, 0),
            ("Pocket Money - Dad", 0, 0),
            ("Pocket Money - Wife", 0, 0),
            ("Pocket Money - Daughter", 0, 0),
            ("Self - Personal Cash", 0, 0),
            ("Family Support/Remittance", 0, 0),
            ("Childcare/School Fees", 0, 0),
            ("Gifts", 0, 0),
        ],
    ),
    (
        "Personal",
        0,
        0,
        [
            ("Clothing", 0, 0),
            ("Personal Care", 0, 0),
            ("Entertainment", 0, 0),
            ("Hobbies", 0, 0),
        ],
    ),
    (
        "Subscriptions",
        0,
        0,
        [
            ("OTT", 0, 0),
            ("Music", 0, 0),
            ("Cloud/Software", 0, 0),
            ("News/Reading", 0, 0),
            ("Other Recurring", 0, 0),
        ],
    ),
    (
        "Financial",
        0,
        0,
        [
            ("Investment-SIP", 0, 0),
            ("Investment-Lumpsum", 0, 0),
            ("Investment-Stocks", 0, 0),
            ("Investment-FD", 0, 0),
            ("Insurance Premium-Life", 0, 0),
            ("Insurance Premium-Vehicle", 0, 0),
            ("Loan-EMI", 0, 0),
            ("Credit Card Bill Payment", 0, 0),
            ("Bank Fees/Charges", 0, 0),
        ],
    ),
    (
        "Taxes",
        0,
        0,
        [
            ("Income Tax", 0, 0),
            ("GST", 0, 0),
            ("Property Tax", 0, 0),
        ],
    ),
    (
        "Transfers",
        1,
        0,
        [
            ("Inter-account Transfer", 1, 0),
            ("Cash Withdrawal (to envelope)", 1, 0),
            ("Reimbursement", 1, 0),
        ],
    ),
    ("Uncategorized", 0, 0, []),
]


async def seed_default_categories(session: AsyncSession) -> int:
    """Idempotently seed default categories. Returns count of newly inserted rows."""
    existing = (await session.execute(select(Category))).scalars().all()
    existing_keys = {(c.name, c.parent_id) for c in existing}

    inserted = 0
    order = 100
    for parent_name, parent_transfer, parent_income, children in DEFAULT_CATEGORIES:
        if (parent_name, None) not in existing_keys:
            parent = Category(
                name=parent_name,
                parent_id=None,
                is_transfer=parent_transfer,
                is_income=parent_income,
                display_order=order,
            )
            session.add(parent)
            await session.flush()
            existing_keys.add((parent_name, None))
            inserted += 1
        else:
            parent = next(c for c in existing if c.name == parent_name and c.parent_id is None)
        order += 10

        child_order = 100
        for child_name, child_transfer, child_income in children:
            if (child_name, parent.id) not in existing_keys:
                session.add(
                    Category(
                        name=child_name,
                        parent_id=parent.id,
                        is_transfer=child_transfer,
                        is_income=child_income,
                        display_order=child_order,
                    )
                )
                existing_keys.add((child_name, parent.id))
                inserted += 1
            child_order += 10

    if inserted:
        await session.commit()
    return inserted
