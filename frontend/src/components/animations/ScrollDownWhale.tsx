"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Environment, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import * as SkeletonUtils from "three/examples/jsm/utils/SkeletonUtils.js";

/* ═══════════════════════════════════════════════════════════════
   ScrollDownWhale — a real 3D humpback that swims DOWN the page
   along an undulating sine path as you scroll, weaving through the
   text. Self-contained transparent R3F canvas overlaid above the
   content (pointer-events-none). Independent of OceanScene.
   ═══════════════════════════════════════════════════════════════ */

const MODEL = "/models/humpback_whale.glb";
useGLTF.preload(MODEL);

const FORWARD = new THREE.Vector3(0, 0, 1); // model nose axis at identity

/** Element the whale "arrives" at — it swims down from above into this. */
const ANCHOR_ID = "problem-section";

/** Live descent progress shared across frames.
 *  Negative → whale still above the viewport (hasn't arrived yet).
 *  0 → entering at the anchor ("The Problem").  1 → page bottom (the depths). */
function useScrollProgress() {
  const ref = useRef(-0.4);
  useEffect(() => {
    const onScroll = () => {
      const vh = window.innerHeight;
      const exit = document.documentElement.scrollHeight - vh;
      const el = document.getElementById(ANCHOR_ID);
      // Absolute document Y of the anchor's top.
      const anchorTop = el
        ? el.getBoundingClientRect().top + window.scrollY
        : vh * 0.9;
      // Whale begins entering only ~0.15 viewport before the anchor reaches
      // the top, so it stays away until the night sky has scrolled off and the
      // section is darkening into view.
      const enter = anchorTop - vh * 0.15;
      const denom = Math.max(1, exit - enter);
      const raw = (window.scrollY - enter) / denom;
      ref.current = Math.min(1, Math.max(-0.4, raw));
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

/* ── Path geometry ───────────────────────────────────────────
   The whale descends from TOP_Y to BOT_Y as progress 0→1, while
   weaving side-to-side in X (the "undulating path through the
   text"). Negative progress parks it above TOP_Y — off-screen —
   so it only swims into shot at the anchor section. The body
   pitches/turns along the tangent of that path. */
const TOP_Y = 20; // world Y where the whale enters at the top
const BOT_Y = -20; // world Y at the bottom (the depths)
const SWAY = 13.5; // horizontal amplitude (world units) — wide swing
const WAVES = 2.0; // number of full S-bends down the page

function pathAt(p: number, out: THREE.Vector3) {
  const y = TOP_Y + (BOT_Y - TOP_Y) * p;
  const x = Math.sin(p * WAVES * Math.PI * 2) * SWAY;
  out.set(x, y, 0);
  return out;
}

function Whale() {
  const groupRef = useRef<THREE.Group>(null);
  const gltf = useGLTF(MODEL);
  const progress = useScrollProgress();

  // Smoothed progress (trails the real scroll for a gliding feel).
  const smoothP = useRef(-0.4);
  const prevPos = useRef(new THREE.Vector3(0, TOP_Y, 0));
  const tmpPos = useRef(new THREE.Vector3());
  const tmpVel = useRef(new THREE.Vector3());
  const targetQuat = useRef(new THREE.Quaternion());

  // Clone (SkeletonUtils preserves skinned-mesh bone bindings) and tint
  // the materials slightly translucent so text stays readable beneath.
  const scene = useMemo(() => {
    const clone = SkeletonUtils.clone(gltf.scene);
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        const apply = (m: THREE.Material) => {
          const c = m.clone();
          c.transparent = true;
          c.opacity = 0.82;
          c.depthWrite = true;
          if (c instanceof THREE.MeshStandardMaterial) {
            c.envMapIntensity = 1.8;
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
    return clone;
  }, [gltf.scene]);

  const mixer = useRef<THREE.AnimationMixer | null>(null);
  useEffect(() => {
    if (!gltf.animations.length) return;
    const m = new THREE.AnimationMixer(scene);
    // Prefer a looping swim cycle; fall back to the first clip.
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

  useFrame((_, delta) => {
    const g = groupRef.current;
    if (!g) return;

    const target = progress.current;

    // Before the anchor section, the whale hasn't "arrived" yet — keep it
    // hidden and snapped to the target so scrolling back up never reveals it
    // gliding through the night sky. It simply isn't there until you descend.
    if (target <= 0.005) {
      smoothP.current = target;
      g.visible = false;
      prevPos.current.copy(pathAt(target, tmpPos.current));
      return;
    }
    g.visible = true;

    mixer.current?.update(delta);

    // Trailing follow of the scroll position.
    smoothP.current += (target - smoothP.current) * 0.06;
    const pos = pathAt(smoothP.current, tmpPos.current);
    g.position.copy(pos);

    // Heading from the on-screen velocity (finite difference). When the
    // page is still, keep the last heading instead of snapping.
    tmpVel.current.subVectors(pos, prevPos.current);
    if (tmpVel.current.lengthSq() > 1e-6) {
      tmpVel.current.normalize();
      targetQuat.current.setFromUnitVectors(FORWARD, tmpVel.current);
    }
    prevPos.current.copy(pos);
    g.quaternion.slerp(targetQuat.current, 0.08);

    // Gentle continuous bank for life.
    const t = performance.now() * 0.001;
    g.rotateZ(Math.sin(t * 0.6) * 0.0025);
  });

  return (
    <group ref={groupRef} position={[0, TOP_Y, 0]} visible={false}>
      <primitive object={scene} scale={0.5} />
    </group>
  );
}

export default function ScrollDownWhale() {
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
    <div className="pointer-events-none fixed inset-0 z-20 hidden lg:block">
      <Canvas
        gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 42], fov: 50 }}
        style={{ background: "transparent" }}
      >
        <Environment preset="sunset" background={false} />
        <ambientLight intensity={0.7} color={0x668aa8} />
        <directionalLight position={[6, 30, 18]} intensity={1.6} color={0x9cc6e6} />
        <directionalLight position={[-12, 6, -10]} intensity={0.5} color={0x3a6fb0} />
        <Suspense fallback={null}>
          <Whale />
        </Suspense>
      </Canvas>
    </div>
  );
}
