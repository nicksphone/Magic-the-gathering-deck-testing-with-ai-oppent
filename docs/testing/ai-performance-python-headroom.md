# Exact AI query reuse and Python performance headroom

The search and rules patch batches printed-trigger source queries, memoizes
only printed trigger text, shares a read scope for paid mana candidates and
ranks legal offers in the same scope as move generation. It caches ordered
legal offers only inside an existing immutable query scope and returns a
detached copy to each caller. Engine transitions still execute normally.
There is no transposition cache across independently mutated branches.

On the paired archived main1 sample, all 12 complete actions and their
resulting snapshot, RNG and card order matched. Four timeout peaks used
234.404 CPU seconds before and 208.524 after, an 11.0% reduction. Eight
resolved checkpoint decisions used 4.904 and 4.298 CPU seconds, a 12.4%
reduction. These are local decision measurements with no whole-game
forecast.

A candidate-only repeat in the isolated worktree matched all 12 recorded
transitions again. The four peaks took 199.887 CPU seconds and the eight
resolved decisions took 4.394 CPU seconds. The paired run is the basis for
the speedup estimates above.

The prior bounded cycle profile attributed 38.8% of decision CPU to copies
and 56.0% to move generation and simulated rules combined. At that mix,
making copies 2–5× faster and removing one quarter of the latter CPU
would give about **1.5–1.8×** on the whole choice, assuming free cache keys
and unchanged remaining work. This is a conditional Python target, not a
measured gain. The previously measured full-state key cost exceeded the
original decision CPU. Keep exact reuse scoped until a cheaper state
identity is available. The available evidence does not establish a path
to 5× from local query caches or from rewriting only the copier.
[Cycle profile and key measurements](python-native-performance-spike-20261117.md)

Reprofile after the copy and verification changes before selecting a native
candidate. If copying still dominates, prototype an exact metadata graph
copy behind the existing Python copier's fallback boundary in C++ with
pybind11 when the Python headers are available. Keep callbacks, foreign
copy protocols and arbitrary Python state in Python. Measure Python/native
conversion and whole-decision latency before integrating it. Use paired
archived choices and differential cases for aliasing, nested cycles,
card order, RNG, incompatible inputs and exceptions, then require replay,
handler/SQLite parity and health checks. This branch adds no build dependency.
