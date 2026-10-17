import React from 'react';
import {createRoot} from 'react-dom/client';
import {Vector3} from 'three';
const v = new Vector3(1, 2, 3);
createRoot(document.getElementById('root')!).render(<main><h1>Witness Fleet toolchain</h1><p>React and Three loaded: {v.length().toFixed(2)}</p></main>);
