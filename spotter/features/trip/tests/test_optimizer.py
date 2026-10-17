"""Tests for the fuel stop optimizer."""

# Standard library imports
import random
from unittest import TestCase

# Spotter imports
from spotter.features.trip.optimizer import Candidate, NoFeasiblePlanError, plan_fuel_stops

RANGE, MPG = 500.0, 10.0


def stations(*pairs: tuple[float, float]) -> list[Candidate[str]]:
    return [Candidate(mile, price, f"s{n}") for n, (mile, price) in enumerate(pairs)]


def brute_force_cost(cands, total, range_miles, mpg, start_fuel):
    """Slow brute-force DP over integer fuel levels, to check plan_fuel_stops against."""
    cands = sorted(cands, key=lambda c: c.mile)
    points = [c.mile for c in cands] + [total]
    prices = [c.price for c in cands]
    rng = int(range_miles)
    inf = float("inf")
    # best[f] = min cost to be at the current point with f miles of fuel.
    best = [inf] * (rng + 1)
    first = int(points[0])
    if first > start_fuel:
        return None
    best[int(start_fuel) - first] = 0.0
    for i in range(len(cands)):
        # Buy any amount here.
        for f in range(rng + 1):
            if best[f] < inf:
                for g in range(f + 1, rng + 1):
                    best[g] = min(best[g], best[f] + (g - f) / mpg * prices[i])
        leg = int(points[i + 1] - points[i])
        nxt = [inf] * (rng + 1)
        for f in range(leg, rng + 1):
            nxt[f - leg] = best[f]
        best = nxt
    return best[0] if best[0] < inf else min((c for c in best if c < inf), default=None)


class OptimizerTest(TestCase):
    def test_trip_within_starting_fuel_needs_no_stops(self):
        plan = plan_fuel_stops(stations((0, 3.0)), 300, RANGE, MPG, start_fuel_miles=400)
        self.assertEqual(plan.stops, [])
        self.assertEqual(plan.total_cost, 0)

    def test_buys_only_what_is_needed_to_finish(self):
        plan = plan_fuel_stops(stations((0, 3.0)), 300, RANGE, MPG)
        self.assertEqual(len(plan.stops), 1)
        self.assertAlmostEqual(plan.total_gallons, 30)
        self.assertAlmostEqual(plan.total_cost, 90)

    def test_buys_just_enough_to_reach_cheaper_station(self):
        plan = plan_fuel_stops(stations((0, 4.0), (100, 3.0)), 450, RANGE, MPG)
        self.assertEqual([s.candidate.ref for s in plan.stops], ["s0", "s1"])
        self.assertAlmostEqual(plan.stops[0].gallons, 10)  # 100 miles at the pricey one
        self.assertAlmostEqual(plan.stops[1].gallons, 35)  # rest at the cheap one
        self.assertAlmostEqual(plan.total_cost, 10 * 4 + 35 * 3)

    def test_fills_up_when_cheapest_in_range(self):
        plan = plan_fuel_stops(stations((0, 3.0), (300, 5.0), (450, 4.0)), 800, RANGE, MPG)
        # Fill 50 gal at $3, skip the $5 one, top up at $4 for the last 300 miles - 50 left.
        self.assertEqual([s.candidate.ref for s in plan.stops], ["s0", "s2"])
        self.assertAlmostEqual(plan.stops[0].gallons, 50)
        self.assertAlmostEqual(plan.stops[1].gallons, 30)
        self.assertAlmostEqual(plan.total_gallons, 80)

    def test_long_trip_requires_multiple_stops(self):
        cands = stations(*[(m, 3.5) for m in range(0, 2800, 200)])
        plan = plan_fuel_stops(cands, 2800, RANGE, MPG)
        self.assertAlmostEqual(plan.total_gallons, 280)
        self.assertGreaterEqual(len(plan.stops), 6)
        for stop in plan.stops:
            self.assertLessEqual(stop.gallons, RANGE / MPG + 1e-9)

    def test_gap_longer_than_range_is_infeasible(self):
        with self.assertRaises(NoFeasiblePlanError) as ctx:
            plan_fuel_stops(stations((0, 3.0), (400, 3.0), (1000, 3.0)), 1200, RANGE, MPG)
        self.assertEqual(ctx.exception.gap_start_mile, 400)

    def test_no_station_reachable_from_start(self):
        with self.assertRaises(NoFeasiblePlanError):
            plan_fuel_stops(stations((50, 3.0)), 300, RANGE, MPG, start_fuel_miles=10)

    def test_matches_brute_force_on_random_routes(self):
        rnd = random.Random(42)
        for _ in range(60):
            total = rnd.randint(100, 1500)
            miles = sorted({0, *(rnd.randint(1, total - 1) for _ in range(rnd.randint(1, 12)))})
            cands = [Candidate(float(m), round(rnd.uniform(2.8, 4.5), 2), m) for m in miles]
            try:
                plan = plan_fuel_stops(cands, total, RANGE, MPG)
            except NoFeasiblePlanError:
                self.assertIsNone(brute_force_cost(cands, total, RANGE, MPG, 0))
                continue
            expected = brute_force_cost(cands, total, RANGE, MPG, 0)
            self.assertIsNotNone(expected)
            self.assertAlmostEqual(plan.total_cost, expected, places=6)
            self.assertAlmostEqual(plan.total_gallons, total / MPG, places=6)

    def test_stop_penalty_skips_stops_that_save_cents(self):
        # Every station is 1 cent cheaper than the previous one, 50 miles apart.
        cands = stations(*[(m, 4.0 - m / 5000) for m in range(0, 1000, 50)])
        cheapest = plan_fuel_stops(cands, 1000, RANGE, MPG)
        practical = plan_fuel_stops(cands, 1000, RANGE, MPG, stop_penalty=5)

        self.assertEqual(len(cheapest.stops), 20)
        self.assertLess(len(practical.stops), 5)
        self.assertGreaterEqual(practical.total_cost, cheapest.total_cost)
        self.assertLess(practical.total_cost - cheapest.total_cost, 5)
        # The penalty is never part of the reported cost.
        self.assertAlmostEqual(
            practical.total_cost, sum(s.gallons * s.candidate.price for s in practical.stops)
        )

    def test_stop_penalty_still_picks_much_cheaper_fuel(self):
        cands = stations((0, 4.0), (100, 3.0))
        plan = plan_fuel_stops(cands, 450, RANGE, MPG, stop_penalty=5)
        # Saving $35 (35 gal * $1) is worth the extra stop.
        self.assertEqual([s.candidate.ref for s in plan.stops], ["s0", "s1"])
