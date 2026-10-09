import type { Machine } from './types';

/** Project the actual configured primitive geometry into a lightweight isometric SVG without loading WebGL. */
export default function MachinePreview({machine}: {machine?: Machine}) {
  const project = (x: number, y: number, z: number) => `${215 + (x - z) * 43},${230 + (x + z) * 17 - y * 53}`;
  const components = [...(machine?.components || [])].sort((a, b) => (a.geometry.position[0] + a.geometry.position[2]) - (b.geometry.position[0] + b.geometry.position[2]));
  return <svg className="machine-art" viewBox="0 0 430 300" fill="none" aria-hidden="true"><ellipse cx="223" cy="258" rx="145" ry="23" fill="#273a35" opacity=".08"/>{components.map(c => {
    const [x, y, z] = c.geometry.position;
    const [width, height, depth] = c.geometry.scale;
    const x0 = x - width / 2, x1 = x + width / 2, y0 = y - height / 2, y1 = y + height / 2, z0 = z - depth / 2, z1 = z + depth / 2;
    return <g key={c.id} fill={c.geometry.color} stroke="#405b5020" strokeWidth=".6"><polygon points={[project(x0, y0, z1), project(x1, y0, z1), project(x1, y1, z1), project(x0, y1, z1)].join(' ')}/><polygon style={{filter:'brightness(.82)'}} points={[project(x1, y0, z0), project(x1, y0, z1), project(x1, y1, z1), project(x1, y1, z0)].join(' ')}/><polygon style={{filter:'brightness(1.12)'}} points={[project(x0, y1, z0), project(x1, y1, z0), project(x1, y1, z1), project(x0, y1, z1)].join(' ')}/></g>;
  })}</svg>;
}
