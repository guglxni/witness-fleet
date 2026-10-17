# Native controller revision approval and contract

User approved revising simulator geometry/controller while keeping strict contact-force, lateral drift and full-corridor delivery acceptance. Native test and disposable measurement execution was separately reapproved after a tool timeout. Graph mutations remain separately blocked.

## Primitive fixture change

The short recovery pusher starts in a declared pre-positioned, non-penetrating pose south of the carton. This is initial fixture configuration only, not commanded teleportation. Motion still advances MuJoCo with finite-force slide actuators; planar omnidirectional primitives do not represent detailed wheel/manipulator dynamics. The pusher is a low-friction compliant primitive; its contact parameters are synthetic, not measured hardware.

Recovery references advance in bounded increments, with maximum position lag, latched push axis and side-then-north parking that does not push through the recovered object. Retain hard acceptance: lateral carton drift <=0.15m, y1.0..1.5m, measured contact peak <=120N, displacement <=1.6m, actual contact and north parking. Actuator force caps are lower than the previous45N; no higher power or waived limits.

Full delivery must cross from west staging to an east-side delivery zone. A 0.3m move at the starting staging site is not corridor acceptance. Fresh local range checks and recovery/scout parking are mandatory before loaded courier travel. Passing native component tests does not prove graph-authorized motion, journal integration or process-crash continuation.
