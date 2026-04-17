def check_large_transactions(df, threshold=100000):
    findings = []

    if "金额" not in df.columns:
        return findings

    for _, row in df.iterrows():
        try:
            amount = float(row["金额"])
            if amount >= threshold:
                findings.append(
                    f"发现大额交易：金额 {amount}"
                )
        except Exception:
            continue

    return findings