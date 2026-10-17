"""Native dependency smoke, not fleet behavior validation."""
import json
import platform
from importlib.metadata import version
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image

XML = '''<mujoco>
<visual><global offwidth="320" offheight="240"/></visual>
<worldbody><light pos="0 0 3"/>
<geom type="plane" size="2 2 .1"/>
<body pos="0 0 .5"><freejoint/>
<geom type="sphere" size=".2" rgba="0 1 0 1" mass="1"/></body>
</worldbody></mujoco>'''
m = mujoco.MjModel.from_xml_string(XML)
d = mujoco.MjData(m)
for _ in range(100):
    mujoco.mj_step(m, d)
assert 0 < d.time < 1
renderer = mujoco.Renderer(m, height=240, width=320)
renderer.update_scene(d)
frame = renderer.render()
assert frame.shape == (240, 320, 3)
assert float(np.std(frame)) > 1
out = Path("artifacts/dependency-smoke")
out.mkdir(parents=True, exist_ok=True)
Image.fromarray(frame).save(out / "mujoco-native.png")
renderer.close()
report = {"platform": platform.platform(), "architecture": platform.machine(),
          "mujoco": version("mujoco"), "steps": 100, "sim_time": d.time,
          "render_shape": list(frame.shape), "render_pixel_std": float(np.std(frame))}
(out / "native.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report))
