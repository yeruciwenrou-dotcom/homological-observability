"""Simulation and projection of complete continuous-time Markov event paths."""

import math

import numpy as np


def simulate_path(q, probability, horizon, rng, *, max_events=100000, labels=None):
    """Direct CTMC simulation; event zero records the initial state."""
    labels = tuple(map(str, range(len(q)))) if labels is None else labels
    state = int(rng.choice(len(q), p=probability))
    times, states = [0.0], [labels[state]]
    time = 0.0
    while True:
        rate = float(-q[state, state])
        if rate == 0:
            break
        next_time = time + float(rng.exponential(1.0 / rate))
        if next_time >= horizon:
            break
        if next_time <= time:
            raise ArithmeticError("event time failed to advance")
        if len(times) - 1 >= max_events:
            raise ValueError("trajectory exceeds the event budget")
        choices = q[state].copy()
        choices[state] = 0
        state = int(rng.choice(len(q), p=choices / rate))
        times.append(next_time)
        states.append(labels[state])
        time = next_time
    return {"times": times, "states": states}


def observe_path(path, grid, model):
    """Validate the whole path, including zero-jump paths, then expose its view."""
    times, states = path["times"], path["states"]
    if (
        not isinstance(times, list)
        or not isinstance(states, list)
        or not times
        or len(times) != len(states)
    ):
        raise ValueError("a trajectory needs aligned nonempty times and states")
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times):
        raise ValueError("event times must be finite numbers")
    if (
        times[0] != 0
        or any(b <= a for a, b in zip(times, times[1:]))
        or times[-1] >= grid[-1]
    ):
        raise ValueError(
            "event times must start at zero and increase strictly before T"
        )
    if any(state not in model.vertices for state in states):
        raise ValueError(
            "path state is outside the support, including its initial state"
        )
    allowed = set(model.edges) | {edge[::-1] for edge in model.edges}
    if any((u, v) not in allowed for u, v in zip(states, states[1:])):
        raise ValueError("path contains a transition outside the support")
    snapshots = [
        states[int(index)] for index in np.searchsorted(times, grid, side="right") - 1
    ]
    counts = {}
    for readout in model.readouts:
        coefficients = readout.as_mapping()
        counts[readout.name] = sum(
            coefficients.get((u, v), 0) - coefficients.get((v, u), 0)
            for u, v in zip(states, states[1:])
        )
    return {"snapshots": snapshots, "readouts": counts}
