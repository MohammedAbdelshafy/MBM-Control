import { useEffect, useRef } from "react";

/**
 * SpiralBackdrop — a living spiral (gyre) rendered on canvas behind the
 * command-center panels. Micro-motion only: a slow rotational drift, a gentle
 * breathing pulse, and a sparse particle field receding toward a focal point.
 * Respects `prefers-reduced-motion` by rendering a single static frame.
 */
export function SpiralBackdrop() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let width = 0;
    let height = 0;
    let dpr = 1;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    // Focal point sits past the right edge: the gyre "recedes" like a tunnel.
    const focalX = () => width * 0.78;
    const focalY = () => height * 0.5;

    type Particle = { x: number; y: number; r: number; speed: number; phase: number };
    let particles: Particle[] = [];

    const seedParticles = () => {
      const count = 90;
      particles = Array.from({ length: count }, (_, i) => {
        const t = i / count;
        return {
          x: (focalX() - width) * Math.pow(t, 2.2) + width * 0.96,
          y: focalY() + (Math.random() - 0.5) * height * (0.15 + 0.85 * t),
          r: 0.5 + Math.random() * 1.3,
          speed: 0.08 + Math.random() * 0.22,
          phase: Math.random() * Math.PI * 2,
        };
      });
    };

    // Archimedean spiral: N arms rotating slowly, alpha fading with distance.
    const drawSpiral = (now: number) => {
      const arms = 4;
      const turns = 3.4;
      const steps = 420;
      const maxR = Math.hypot(width, height) * 0.72;
      const rot = now * 0.05; // slow degrees/sec
      const breathe = 0.5 + 0.5 * Math.sin(now * 0.4);

      ctx.lineWidth = 1.1;
      ctx.lineCap = "round";

      for (let arm = 0; arm < arms; arm++) {
        ctx.beginPath();
        const base = (arm / arms) * Math.PI * 2 + rot;
        for (let i = 0; i <= steps; i++) {
          const t = i / steps;
          const r = t * maxR;
          const th = base + t * turns * Math.PI * 2;
          // pull the gyre toward the focal point so it reads as a receding tunnel
          const x = focalX() + Math.cos(th) * r * 0.94;
          const y = focalY() + Math.sin(th) * r * 0.5;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        const alpha = 0.045 + 0.05 * breathe;
        ctx.strokeStyle = `rgba(6, 182, 212, ${alpha.toFixed(3)})`;
        ctx.stroke();
        // second pass, offset, for a denser weave
        ctx.beginPath();
        for (let i = 0; i <= steps; i++) {
          const t = i / steps;
          const r = t * maxR;
          const th = base + 0.12 + t * turns * Math.PI * 2;
          const x = focalX() + Math.cos(th) * r * 0.94;
          const y = focalY() + Math.sin(th) * r * 0.5;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(94, 234, 212, ${(alpha * 0.6).toFixed(3)})`;
        ctx.stroke();
      }
    };

    // Concentric perspective rings receding to the focal point.
    const drawRings = (now: number) => {
      const rings = 7;
      const pulse = 0.5 + 0.5 * Math.sin(now * 0.5);
      for (let i = 0; i < rings; i++) {
        const t = i / (rings - 1);
        const rx = width * (0.06 + 0.6 * t);
        const ry = rx * 0.42;
        ctx.beginPath();
        ctx.ellipse(focalX(), focalY(), rx, ry, 0, 0, Math.PI * 2);
        const alpha = (0.028 + 0.035 * t) * (0.7 + 0.3 * pulse);
        ctx.strokeStyle = `rgba(34, 211, 238, ${alpha.toFixed(3)})`;
        ctx.lineWidth = 0.7;
        ctx.stroke();
      }
    };

    const drawParticles = (now: number) => {
      for (const p of particles) {
        // drift toward focal point (tunnel pull), twinkle with phase
        const dx = focalX() - p.x;
        const dy = focalY() - p.y;
        const dist = Math.hypot(dx, dy) || 1;
        p.x += (dx / dist) * p.speed * 0.55;
        p.y += (dy / dist) * p.speed * 0.55;
        if (dist < 2) {
          p.x = width * (0.5 + Math.random() * 0.5);
          p.y = Math.random() * height;
        }
        const twinkle = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(now * 1.5 + p.phase));
        ctx.beginPath();
        ctx.fillStyle = `rgba(125, 240, 255, ${(twinkle * 0.5).toFixed(3)})`;
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const frame = (nowMs: number) => {
      ctx.clearRect(0, 0, width, height);
      const now = reduced ? 0 : nowMs / 1000;
      drawSpiral(now);
      drawRings(now);
      drawParticles(now);
      if (!reduced) raf = requestAnimationFrame(frame);
      else setTimeout(() => {}, 0);
    };

    resize();
    seedParticles();

    if (reduced) {
      frame(0);
    } else {
      raf = requestAnimationFrame(frame);
    }

    const onResize = () => {
      resize();
      seedParticles();
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 h-full w-full opacity-100"
    />
  );
}
