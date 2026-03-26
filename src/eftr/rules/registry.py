"""Maps rule_type → handler function."""
from src.eftr.rules.handlers import (
    deadline,
    fx_conversion,
    mandatory_fields,
    over_reporting,
    threshold,
)

# Registry maps rule_code to a callable that takes (eft_df, rep_df, reported_ids, rule) -> list[dict]
# Handlers have different signatures; this registry normalizes them via lambdas.

RULE_REGISTRY = {
    "FINTRAC_SINGLE_THRESHOLD":  lambda eft, rep, rep_ids, rule: threshold.evaluate(eft, rep, rep_ids, rule),
    "FINTRAC_FILING_DEADLINE":   lambda eft, rep, rep_ids, rule: deadline.evaluate(eft, rep, rep_ids, rule),
    "FINTRAC_MANDATORY_FIELDS":  lambda eft, rep, rep_ids, rule: mandatory_fields.evaluate(eft, rep, rep_ids, rule),
    "FINTRAC_TRAVEL_RULE":       lambda eft, rep, rep_ids, rule: mandatory_fields.evaluate(eft, rep, rep_ids, rule),
    "FINTRAC_FX_CONVERSION":     lambda eft, rep, rep_ids, rule: fx_conversion.evaluate(eft, rep, rule),
    "FINTRAC_OVER_REPORTING":    lambda eft, rep, rep_ids, rule: over_reporting.evaluate(eft, rep_ids, rule),
}
