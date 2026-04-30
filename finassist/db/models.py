from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from db.types import DecimalText


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "type IN ('bank','credit_card','cash_envelope','broker','mf','epf','nps')",
            name="ck_accounts_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    bank_code: Mapped[str | None] = mapped_column(String)
    account_number_masked: Mapped[str | None] = mapped_column(String)
    envelope_owner: Mapped[str | None] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    opening_balance: Mapped[Decimal] = mapped_column(
        DecimalText, nullable=False, default=Decimal("0")
    )
    opening_balance_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "parent_id", name="uq_categories_name_parent"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE")
    )
    is_transfer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_income: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    display_order: Mapped[int | None] = mapped_column(Integer, default=100)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "cadence IN ('monthly','quarterly','annual','custom')",
            name="ck_subscriptions_cadence",
        ),
        CheckConstraint(
            "status IN ('active','paused','cancelled')",
            name="ck_subscriptions_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expected_amount: Mapped[Decimal | None] = mapped_column(DecimalText)
    amount_tolerance_pct: Mapped[float] = mapped_column(nullable=False, default=5.0)
    cadence: Mapped[str | None] = mapped_column(String)
    next_expected_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    started_on: Mapped[date | None] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String)
    auto_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type IN ('debit','credit')", name="ck_transactions_type"),
        CheckConstraint(
            "classification_source IN "
            "('rule_t1','rule_t2','fuzzy_t3','manual','unclassified')",
            name="ck_transactions_classification_source",
        ),
        CheckConstraint(
            "review_reason IN ('classification','duplicate','transfer')",
            name="ck_transactions_review_reason",
        ),
        Index("idx_txn_date", "txn_date"),
        Index("idx_txn_category", "category_id"),
        Index("idx_txn_subscription", "subscription_id"),
        Index(
            "idx_txn_review",
            "needs_review",
            sqlite_where=text("needs_review=1"),
        ),
        Index("idx_txn_account_date", "account_id", "txn_date"),
        Index(
            "idx_txn_dup_group",
            "dup_group_id",
            sqlite_where=text("dup_group_id IS NOT NULL"),
        ),
        Index(
            "idx_txn_dedup_lookup",
            "account_id",
            "txn_date",
            "amount",
            "narration_hash",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    narration: Mapped[str] = mapped_column(String, nullable=False)
    narration_hash: Mapped[str] = mapped_column(String, nullable=False)
    balance_after: Mapped[Decimal | None] = mapped_column(DecimalText)
    reference: Mapped[str | None] = mapped_column(String)
    value_date: Mapped[date | None] = mapped_column(Date)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"))
    transfer_pair_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"))
    is_transfer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    classification_source: Mapped[str | None] = mapped_column(String, default="unclassified")
    classification_confidence: Mapped[float | None] = mapped_column()
    needs_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String)
    dup_group_id: Mapped[int | None] = mapped_column(Integer)
    review_reason: Mapped[str | None] = mapped_column(String)
    source_file: Mapped[str | None] = mapped_column(String)
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_line: Mapped[int | None] = mapped_column(Integer)
    raw_narration: Mapped[str | None] = mapped_column(String)
    raw_date_str: Mapped[str | None] = mapped_column(String)
    raw_amount_str: Mapped[str | None] = mapped_column(String)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (
        CheckConstraint(
            "pattern_type IN ('narration','vpa','prefix','token','exact')",
            name="ck_rules_pattern_type",
        ),
        CheckConstraint("txn_type IN ('debit','credit')", name="ck_rules_txn_type"),
        CheckConstraint(
            "status IN ('candidate','active','disabled','blacklisted')",
            name="ck_rules_status",
        ),
        CheckConstraint("created_by IN ('system','user')", name="ck_rules_created_by"),
        Index("idx_rules_status", "status"),
        Index("idx_rules_priority", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String, nullable=False)
    pattern_type: Mapped[str | None] = mapped_column(String)
    amount_min: Mapped[Decimal | None] = mapped_column(DecimalText)
    amount_max: Mapped[Decimal | None] = mapped_column(DecimalText)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    txn_type: Mapped[str | None] = mapped_column(String)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"))
    status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime)
    blacklist_until: Mapped[datetime | None] = mapped_column(DateTime)


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        CheckConstraint(
            "instrument_type IN ('mf','stock','fd','epf','nps','crypto')",
            name="ck_holdings_instrument_type",
        ),
        UniqueConstraint("account_id", "identifier", name="uq_holdings_account_identifier"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String, nullable=False)
    identifier: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    units: Mapped[Decimal] = mapped_column(DecimalText, nullable=False, default=Decimal("0"))
    avg_cost: Mapped[Decimal | None] = mapped_column(DecimalText)
    total_invested: Mapped[Decimal] = mapped_column(
        DecimalText, nullable=False, default=Decimal("0")
    )
    current_nav: Mapped[Decimal | None] = mapped_column(DecimalText)
    current_value: Mapped[Decimal | None] = mapped_column(DecimalText)
    nav_updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class HoldingTransaction(Base):
    __tablename__ = "holding_transactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('buy','sell','dividend','split','bonus')",
            name="ck_holding_transactions_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    holding_id: Mapped[int] = mapped_column(ForeignKey("holdings.id"), nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    units: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    price_per_unit: Mapped[Decimal | None] = mapped_column(DecimalText)
    amount: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    linked_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"))
    notes: Mapped[str | None] = mapped_column(String)


class Import(Base):
    __tablename__ = "imports"
    __table_args__ = (
        CheckConstraint(
            "source_format IN ('pdf','csv','xlsx','manual')",
            name="ck_imports_source_format",
        ),
        CheckConstraint("status IN ('success','partial','failed')", name="ck_imports_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    source_file: Mapped[str | None] = mapped_column(String)
    source_format: Mapped[str | None] = mapped_column(String)
    bank_code: Mapped[str | None] = mapped_column(String)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    rows_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str | None] = mapped_column(String)
    error_log: Mapped[str | None] = mapped_column(String)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class NavCache(Base):
    __tablename__ = "nav_cache"
    __table_args__ = (UniqueConstraint("scheme_code", "nav_date", name="uq_nav_cache_scheme_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_code: Mapped[str] = mapped_column(String, nullable=False)
    scheme_name: Mapped[str | None] = mapped_column(String)
    nav: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
