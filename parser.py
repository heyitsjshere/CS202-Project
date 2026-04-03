class RCPSPInstance:
    def __init__(self):
        self.n = 0
        self.num_resources = 0
        self.durations = []
        self.demands = []
        self.resources = []
        self.precedence = []


def parse_sch(filepath):
    inst = RCPSPInstance()

    with open(filepath, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    def parse_ints(raw_line):
        # Faster than regex for this dataset; also supports values like [-22].
        cleaned = raw_line.replace("[", " ").replace("]", " ")
        return [int(x) for x in cleaned.split()]

    idx = 0
    header = parse_ints(lines[idx])
    if len(header) < 2:
        raise ValueError(f"Invalid SCH header in {filepath}")

    n_activities_without_dummies = header[0]
    r = header[1]
    expected_n = n_activities_without_dummies + 2
    idx += 1

    precedence = []
    seen_ids = set()

    for _ in range(expected_n):
        parts = parse_ints(lines[idx])
        idx += 1
        if len(parts) < 2:
            raise ValueError(f"Invalid precedence row in {filepath}: {lines[idx - 1]}")

        i = parts[0]
        # Supported precedence formats:
        # 1) i k succ1 succ2 ...
        # 2) i mode k succ1 succ2 ...
        if len(parts) == 2:
            # format (1), no successors
            k = parts[1]
            successors = []
        elif len(parts) >= 3 and len(parts) == parts[1] + 2:
            # format (1)
            k = parts[1]
            successors = parts[2:2 + k] if k > 0 else []
        else:
            # format (2) fallback
            if len(parts) < 3:
                raise ValueError(f"Invalid precedence row in {filepath}: {lines[idx - 1]}")
            k = parts[2]
            successors = parts[3:3 + k] if k > 0 else []

        seen_ids.add(i)
        for j in successors:
            precedence.append((i, j))
            seen_ids.add(j)

    if not seen_ids:
        raise ValueError(f"No activities found in {filepath}")

    n = max(max(seen_ids) + 1, expected_n)

    durations = [0] * n
    demands = [[0] * r for _ in range(n)]

    for _ in range(expected_n):
        parts = parse_ints(lines[idx])
        idx += 1
        if len(parts) < 2:
            raise ValueError(f"Invalid duration row in {filepath}: {lines[idx - 1]}")

        i = parts[0]
        # Supported duration formats:
        # 1) i duration d1 d2 ... dR
        # 2) i mode duration d1 d2 ... dR
        if len(parts) >= 2 + r and len(parts) == 2 + r:
            # format (1)
            duration = parts[1]
            demand_values = parts[2:2 + r]
        else:
            # format (2) fallback
            if len(parts) < 3:
                raise ValueError(f"Invalid duration row in {filepath}: {lines[idx - 1]}")
            duration = parts[2]
            demand_values = parts[3:3 + r]

        if len(demand_values) < r:
            demand_values += [0] * (r - len(demand_values))

        durations[i] = duration
        demands[i] = demand_values

    capacities = parse_ints(lines[idx])
    if len(capacities) < r:
        raise ValueError(f"Invalid resource capacity row in {filepath}: {lines[idx]}")

    inst.n = n
    inst.num_resources = r
    inst.precedence = precedence
    inst.durations = durations
    inst.demands = demands
    inst.resources = capacities[:r]

    return inst