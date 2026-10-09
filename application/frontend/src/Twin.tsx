import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import type { ComponentSpec } from './types';

/** Render only server-approved, data-driven primitives; Canvas errors are caught by the parent boundary. */
export default function Twin({components, selected, onSelect}: {components: ComponentSpec[]; selected: string; onSelect: (id: string) => void}) {
  return <Canvas frameloop="demand" dpr={[1, 1.5]} camera={{position: [5.5, 4, 6], fov: 40}} gl={{antialias: true, powerPreference: 'low-power'}} onCreated={({gl}) => {gl.setClearColor('#edf1ed');}}>
    <ambientLight intensity={1.7}/><directionalLight position={[4, 7, 4]} intensity={2.5}/><directionalLight position={[-4, 2, 0]} intensity={.6}/>
    <group position={[0, -.3, 0]}>{components.map(c => <mesh key={c.id} position={c.geometry.position} scale={c.geometry.scale} onClick={e => {e.stopPropagation(); onSelect(c.id);}}>
      {c.geometry.shape === 'cylinder' ? <cylinderGeometry args={[.5, .5, 1, 24]}/> : <boxGeometry args={[1, 1, 1]}/>}
      <meshStandardMaterial color={selected === c.id ? '#b4e88b' : c.geometry.color} roughness={.55} metalness={.2}/>
    </mesh>)}</group><Grid position={[0, -.45, 0]} args={[12, 12]} cellSize={.5} cellThickness={.5} cellColor="#c9d1cd" sectionSize={2} sectionThickness={.75} sectionColor="#b7c1ba" fadeDistance={14} infiniteGrid/>
    <OrbitControls makeDefault target={[0, 1, 0]} minDistance={3} maxDistance={12} maxPolarAngle={Math.PI / 2.05}/>
  </Canvas>;
}
