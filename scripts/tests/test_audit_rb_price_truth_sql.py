from pathlib import Path
import re


SQL_PATH = Path(__file__).resolve().parents[1] / "audit-rb-price-truth.sql"


def sql_text() -> str:
    return SQL_PATH.read_text(encoding="utf-8")


def test_audit_is_read_only() -> None:
    sql = sql_text()
    forbidden = re.compile(
        r"\b(insert|update|delete|merge|alter|drop|truncate|create|grant|revoke|copy)\b",
        re.IGNORECASE,
    )

    assert forbidden.search(sql) is None
    assert sql.count("SELECT jsonb_pretty") == 1


def test_price_eligibility_is_fail_closed() -> None:
    sql = sql_text()

    assert "one_c.price > 0" in sql
    assert "one_c.currency = rb.currency_code" in sql
    assert "nullif(btrim(one_c.price_type), '') IS NOT NULL" in sql
    assert "one_c.updated_at IS NOT NULL" in sql
    assert "eligible_one_c.external_id = rb_products.external_id" in sql
    assert "~ '^[0-9]+([.][0-9]+)?$'" in sql
    assert "ELSE false" in sql


def test_audit_reports_evidence_integrity_and_safe_batch() -> None:
    sql = sql_text()

    for key in (
        "visible_price_without_current_evidence",
        "current_evidence_visible_price_mismatch",
        "duplicate_current_evidence_products",
        "safe_next_one_c_x2_batch",
    ):
        assert key in sql
