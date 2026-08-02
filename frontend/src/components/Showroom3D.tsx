import { Component, Suspense, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Canvas } from '@react-three/fiber'
import { ContactShadows, OrbitControls } from '@react-three/drei'
import type { Product } from '../types'
import { ProductVisual } from './ui'

class SceneErrorBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

function ProductMesh({ product, index, selected, onSelect }: { product: Product; index: number; selected: boolean; onSelect: () => void }) {
  const config = useMemo(() => {
    try { return JSON.parse(product.model_config) } catch { return { shape: 'box', color: '#44a8ff' } }
  }, [product.model_config])
  const positions: [number, number, number][] = [[-3.2, .8, 0], [-1.6, .75, -.4], [0, .65, 0], [1.6, .75, -.4], [3.2, .8, 0]]
  const pos = positions[index % positions.length]
  const geometry = config.shape === 'sphere' ? <sphereGeometry args={[.68, 32, 32]} /> : config.shape === 'cylinder' ? <cylinderGeometry args={[.52, .65, 1.5, 32]} /> : config.shape === 'cone' ? <coneGeometry args={[.72, 1.45, 32]} /> : <boxGeometry args={[1.15, 1.1, .9]} />
  return <group position={pos} onClick={(event) => { event.stopPropagation(); onSelect() }}>
    <mesh castShadow scale={selected ? 1.12 : 1}>
      {geometry}
      <meshStandardMaterial color={config.color} metalness={.38} roughness={.28} emissive={selected ? config.color : '#000'} emissiveIntensity={selected ? .22 : 0} />
    </mesh>
    <mesh position={[0, -.88, 0]} receiveShadow><cylinderGeometry args={[.82, .92, .16, 32]} /><meshStandardMaterial color={selected ? '#2d8bcf' : '#18314c'} metalness={.55} roughness={.32} /></mesh>
    {product.popularity >= 90 && <mesh position={[.55, .9, 0]}><sphereGeometry args={[.11, 16, 16]} /><meshBasicMaterial color="#ff6d7f" /></mesh>}
  </group>
}

function Scene({ products, selected, onSelect, theme }: { products: Product[]; selected: number; onSelect: (index: number) => void; theme: string }) {
  const floor = theme === 'jade' ? '#0c2f32' : theme === 'warm' ? '#38291f' : '#091a2d'
  return <>
    <color attach="background" args={[theme === 'warm' ? '#201713' : '#06111f']} />
    <fog attach="fog" args={[theme === 'warm' ? '#201713' : '#06111f', 8, 18]} />
    <ambientLight intensity={.8} />
    <directionalLight position={[5, 7, 5]} intensity={2.4} castShadow />
    <pointLight position={[-5, 2, 1]} color="#44a8ff" intensity={12} distance={8} />
    <pointLight position={[5, 2, 1]} color={theme === 'jade' ? '#31c6a4' : '#8e7cff'} intensity={10} distance={8} />
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow><planeGeometry args={[18, 12]} /><meshStandardMaterial color={floor} metalness={.22} roughness={.64} /></mesh>
    <mesh position={[0, 2.2, -2.8]}><boxGeometry args={[9.5, 4.4, .15]} /><meshStandardMaterial color={theme === 'warm' ? '#392b23' : '#0d2740'} metalness={.25} roughness={.5} /></mesh>
    {products.slice(0, 5).map((product, index) => <ProductMesh key={product.id} product={product} index={index} selected={selected === index} onSelect={() => onSelect(index)} />)}
    <ContactShadows position={[0, .02, 0]} opacity={.55} scale={12} blur={2.5} far={5} />
    <OrbitControls makeDefault minDistance={5} maxDistance={11} maxPolarAngle={Math.PI / 2.1} target={[0, .7, 0]} />
  </>
}

export function ShowroomCanvas({ products, selected, onSelect, theme, force2D }: { products: Product[]; selected: number; onSelect: (index: number) => void; theme: string; force2D: boolean }) {
  const [webglLost, setWebglLost] = useState(false)
  const fallback = <div className="showroom-2d"><div className="fallback-banner">3D模式不可用，已自动切换为2D展厅</div><div className="showroom-2d-grid">{products.slice(0, 5).map((product, index) => <button key={product.id} className={selected === index ? 'selected' : ''} onClick={() => onSelect(index)}><ProductVisual variant={index} /><strong>{product.name}</strong><span>${product.price} · MOQ {product.moq}</span></button>)}</div></div>
  if (force2D || webglLost) return fallback
  return <SceneErrorBoundary fallback={fallback}><div className="canvas-wrap"><Canvas shadows camera={{ position: [0, 3.2, 7.8], fov: 42 }} onCreated={({ gl }) => gl.domElement.addEventListener('webglcontextlost', () => setWebglLost(true))}><Suspense fallback={null}><Scene products={products} selected={selected} onSelect={onSelect} theme={theme} /></Suspense></Canvas><div className="canvas-hint">拖拽旋转 · 滚轮缩放 · 点击商品</div></div></SceneErrorBoundary>
}
