# Mirrored Combat Fixture Capture

Base: `2eeb7f769aa8b2a02e0b6e4cb14dc98ecf7f8e17`. Its hosted browser run
passed the first direct-combat seat, then received HTTP500 when publishing the
second-seat fixture. This is not a whole-browser pass.

The fixture reverses player and card ownership after constructing the original
stock. Its new private sideboard inventory still referred to the original
owners, so the strict snapshot validator correctly rejected that stale binding.
An exact route-body/serializer reproduction completed three failures and eighteen
passes before the fix, with no SQL or server import.

Only the mirrored synthetic fixture now explicitly sets private capture to `{}`,
the existing unknown/unqualified form. It does not invent replacement stock,
certify sideboarding, change public observations or relax the validator. Normal
Factory capture, API actions and production sideboarding are untouched. All
original browser assertions and the nine band/four direct-view tests are retained.

The same three whole pure modules pass all 21 ordinary cases in 4.446 seconds,
zero failures/errors/skips. Eight new cases cover both-seat snapshot restoration,
checked band/block actions, rejection atomicity and continued rejection of forged
real ownership bindings. Whole-module source outside the two added fixture lines
and the new test is unchanged; independent static review confirms that scope.

The original `browser-direct-combat.mjs` also ran once through the existing
browser harness, on an isolated source copy and fresh local SQLite. Both physical
seats passed real pointer selection, legal band submission, illegal flying-block
rejection, click/drag assignment and authoritative block propagation. The driver
and its assertions are byte-unchanged. The focused script exited zero at
2026-10-13T09:22:23Z; it is not the complete browser cohort.

Uvicorn completed graceful application shutdown, the fixed loopback services
closed, external `fuser` returned1 with empty output for both owned database files,
and both closed databases passed integrity checks. The SQL slot was released at
09:24:31.236931Z. Cached dependencies were reused, not described as a new install.
No live server or user data was modified; raw source/profile/database evidence
remains private archive material.

Complete hosted qualification on the corrected source, natural sideboarding,
measured AI strength and the original RC1 release requirements remain open.
