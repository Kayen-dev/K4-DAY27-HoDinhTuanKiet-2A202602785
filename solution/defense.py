"""Single-pass data pipeline checks using only the published toolkit API."""
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def _verdict(pillar, reasons):
    return Verdict(alert=bool(reasons), pillar=pillar, reason=", ".join(reasons))


def _available(result):
    return isinstance(result, dict) and "error" not in result


def _inside_calibrated_range(value, minimum, maximum):
    # Published endpoints are mean +/- 3 sigma. A 2.5 sigma guard captures
    # smaller changes while retaining the published clean-stream calibration.
    margin = (maximum - minimum) / 12.0
    return minimum + margin <= value <= maximum - margin


def check_data_batch(payload, ctx):
    profile = ctx.tools.batch_profile(payload["batch_id"])
    if not _available(profile):
        return _verdict("checks", [])
    b = ctx.baseline
    reasons = []
    if not _inside_calibrated_range(profile["row_count"], b["row_count_min"], b["row_count_max"]):
        reasons.append("volume")
    if profile["null_rate"]["customer_id"] > b["null_rate_max"]:
        reasons.append("customer_id null rate")
    if not _inside_calibrated_range(profile["mean_amount"], b["mean_amount_min"], b["mean_amount_max"]):
        reasons.append("amount distribution")
    if profile["staleness_min"] > b["staleness_min_max"]:
        reasons.append("staleness")
    return _verdict("checks", reasons)


def check_contract_checkpoint(payload, ctx):
    diff = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    if not _available(diff):
        return _verdict("contracts", [])
    reasons = list(diff["violations"])
    if diff["freshness_delay_min"] > ctx.baseline["freshness_delay_max_min"]:
        reasons.append("freshness SLA")
    return _verdict("contracts", reasons)


def check_lineage_run(payload, ctx):
    graph = ctx.tools.lineage_graph_slice(payload["run_id"])
    if not _available(graph):
        return _verdict("lineage", [])
    reasons = []
    # The staging job joins orders with customer records; its event envelope
    # lists the triggering input, while the graph reports all required parents.
    expected_by_job = {"dbt:stg_orders": {"raw.orders", "raw.customers"}}
    expected_upstream = expected_by_job.get(payload.get("job"))
    if expected_upstream is not None and not expected_upstream.issubset(set(graph["actual_upstream"])):
        reasons.append("upstream edges")
    expected_downstream = len(payload.get("outputs", []))
    if expected_downstream and graph["actual_downstream_count"] < expected_downstream:
        reasons.append("downstream edges")
    if graph["duration_ms"] > ctx.baseline["lineage_duration_ms_max"]:
        reasons.append("runtime")
    return _verdict("lineage", reasons)


def check_feature_materialization(payload, ctx):
    drift = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    if not _available(drift):
        return _verdict("ai_infra", [])
    reasons = []
    if drift["mean_shift_sigma"] > 0.9 * ctx.baseline["feature_mean_shift_sigma_max"]:
        reasons.append("training-serving skew")
    return _verdict("ai_infra", reasons)


def check_embedding_batch(payload, ctx):
    drift = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    if not _available(drift):
        return _verdict("ai_infra", [])
    reasons = []
    if drift["centroid_shift"] > 0.9 * ctx.baseline["embedding_centroid_shift_max"]:
        reasons.append("embedding drift")
    if drift["avg_doc_age_days"] > ctx.baseline["corpus_avg_doc_age_days_max"]:
        reasons.append("corpus staleness")
    return _verdict("ai_infra", reasons)
