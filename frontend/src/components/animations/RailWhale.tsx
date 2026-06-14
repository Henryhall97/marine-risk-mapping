"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import * as SkeletonUtils from "three/examples/jsm/utils/SkeletonUtils.js";

/* ═══════════════════════════════════════════════════════════════
   RailWhale — a small, glowing 3D humpback that dives DOWN the
   left depth-gauge rail in lockstep with scroll, mirroring the
   full-size ScrollDownWhale weaving through the page. Its vertical
   position maps the same 0..1 scroll fraction the rail uses, so it
   sits exactly on the rail line. Self-contained transparent R3F
   canvas, pointer-events-none, lg-only.
   ═══════════════════════════════════════════════════════════════ */

const MODEL = "/models/humpback_whale.glb";
useGLTF.preload(MODEL);

/** Raw scroll fraction (0 = page top, 1 = page bottom) — IDENTICAL to the
 *  mapping DepthRail uses for its bead and live depth readout, so the whale
 *  sits exactly on the readout at every scroll position. Stored in a ref so
 *  scrolling never re-renders the canvas. */
function useScrollFraction() {
  const ref = useRef(0);
  useEffect(() => {
    const onScroll = () => {
      const max =
        document.documentElement.scrollHeight - window.innerHeight;
      ref.current =
        max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);
  return ref;
}

function Whale() {
  const gltf = useGLTF(MODEL);
  const groupRef = useRef<THREE.Group>(null);
  const innerRef = useRef<THREE.Group>(null);
  const fraction = useScrollFraction();
  const prevP = useRef(0);
  const pitch = useRef(Math.PI / 2);
  const { viewport } = useThree();

  // Clone (SkeletonUtils preserves skinned-mesh bindings), centre at origin,
  // and give the material a faint cyan glow so it reads on the dark rail.
  const { scene, maxDim } = useMemo(() => {
    const clone = SkeletonUtils.clone(gltf.scene);
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        const apply = (m: THREE.Material) => {
          const c = m.clone();
          if (c instanceof THREE.MeshStandardMaterial) {
            c.emissive = new THREE.Color(0x22d3ee);
            c.emissiveIntensity = 0.35;
            c.envMapIntensity = 1.2;
          }
          return c;
        };
        child.castShadow = false;
        child.receiveShadow = false;
        child.material = Array.isArray(child.material)
          ? child.material.map(apply)
          : apply(child.material);
      }
    });
    // Recentre so the model's bounding-box centre is at the origin.
    const box = new THREE.Box3().setFromObject(clone);
    const center = new THREE.Vector3();
    const size = new THREE.Vector3();
    box.getCenter(center);
    box.getSize(size);
    clone.position.sub(center);
    return { scene: clone, maxDim: Math.max(size.x, size.y, size.z) || 1 };
  }, [gltf.scene]);

  // Looping swim cycle.
  const mixer = useRef<THREE.AnimationMixer | null>(null);
  useEffect(() => {
    if (!gltf.animations.length) return;
    const m = new THREE.AnimationMixer(scene);
    const swim =
      gltf.animations.find((c) => /swim1$/i.test(c.name)) ??
      gltf.animations.find((c) => /swim/i.test(c.name)) ??
      gltf.animations[0];
    const action = m.clipAction(swim);
    action.setLoop(THREE.LoopRepeat, Infinity);
    action.play();
    mixer.current = m;
    return () => {
      m.stopAllAction();
      mixer.current = null;
    };
  }, [scene, gltf.animations]);

  useFrame((state, delta) => {
    const g = groupRef.current;
    const inner = innerRef.current;
    if (!g || !inner) return;
    mixer.current?.update(delta);

    // Vertical position is locked to the RAW scroll fraction (no trailing) so
    // the whale sits exactly on the live depth readout / rail bead — the
    // readout uses the same instantaneous value. Smoothing is kept only for
    // the swim sway + dive/climb pitch below, for an organic feel.
    const p = Math.min(1, Math.max(0, fraction.current));

    // viewport.height/width are the visible world extents of the ortho
    // camera, so mapping progress → [+H/2 .. −H/2] places the whale at the
    // exact pixel fraction down the canvas, aligning it with the rail.
    const h = viewport.height;
    const t = state.clock.elapsedTime;
    const x = Math.sin(t * 0.8) * viewport.width * 0.07;
    const y = h / 2 - p * h;
    g.position.set(x, y, 0);

    // Turn the whale to face its travel direction: nose-down while
    // descending, nose-up when the user scrolls back toward the surface.
    const dy = p - prevP.current;
    prevP.current = p;
    const targetPitch =
      dy < -0.0002
        ? -Math.PI / 2 // heading up (+Y)
        : dy > 0.0002
          ? Math.PI / 2 // heading down (−Y)
          : pitch.current; // idle — keep last facing
    pitch.current += (targetPitch - pitch.current) * 0.08;

    // Fit the whale to ~85% of the (narrow) canvas width, then apply the
    // dive/climb pitch with a gentle sway + bank.
    const scale = (viewport.width * 0.85) / maxDim;
    inner.scale.setScalar(scale);
    inner.rotation.x = pitch.current; // dive (−Y) ↔ climb (+Y)
    inner.rotation.z = Math.sin(t * 0.8) * 0.14; // tail sway
    inner.rotation.y = Math.sin(t * 0.5) * 0.12; // subtle turn
  });

  return (
    <group ref={groupRef}>
      <group ref={innerRef}>
        <primitive object={scene} />
      </group>
    </group>
  );
}

export default function RailWhale() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const wide = window.matchMedia("(min-width: 1024px)");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setEnabled(wide.matches && !reduced.matches);
    update();
    wide.addEventListener("change", update);
    reduced.addEventListener("change", update);
    return () => {
      wide.removeEventListener("change", update);
      reduced.removeEventListener("change", update);
    };
  }, []);

  if (!enabled) return null;

  return (
    <div className="pointer-events-none fixed left-0 top-1/2 z-20 hidden h-[68vh] w-12 -translate-y-1/2 lg:block">
      <Canvas
        orthographic
        gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 10], zoom: 70 }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.9} color={0x88b6d8} />
        <directionalLight position={[4, 8, 10]} intensity={1.5} color={0x9cc6e6} />
        <directionalLight position={[-6, -4, 4]} intensity={0.6} color={0x22d3ee} />
        <Suspense fallback={null}>
          <Whale />
        </Suspense>
      </Canvas>
    </div>
  );
}
