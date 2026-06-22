"use client";

import { CSSProperties, ReactNode, useCallback, useEffect, useRef } from "react";

type BorderGlowProps = {
  children: ReactNode;
  className?: string;
  edgeSensitivity?: number;
  glowColor?: string;
  backgroundColor?: string;
  borderRadius?: number;
  glowRadius?: number;
  glowIntensity?: number;
  coneSpread?: number;
  animated?: boolean;
  colors?: string[];
  fillOpacity?: number;
};

type GlowStyle = CSSProperties & Record<`--${string}`, string | number>;

const gradientPositions = [
  "80% 55%",
  "69% 34%",
  "8% 6%",
  "41% 38%",
  "86% 85%",
  "82% 18%",
  "51% 4%",
];
const gradientKeys = [
  "--gradient-one",
  "--gradient-two",
  "--gradient-three",
  "--gradient-four",
  "--gradient-five",
  "--gradient-six",
  "--gradient-seven",
] as const;
const colorMap = [0, 1, 2, 0, 1, 2, 1];

function parseHsl(hsl: string) {
  const match = hsl.match(/([\d.]+)\s*([\d.]+)%?\s*([\d.]+)%?/);
  if (!match) {
    return { h: 40, s: 80, l: 80 };
  }

  return {
    h: Number.parseFloat(match[1]),
    s: Number.parseFloat(match[2]),
    l: Number.parseFloat(match[3]),
  };
}

function buildGlowVars(glowColor: string, intensity: number): GlowStyle {
  const { h, s, l } = parseHsl(glowColor);
  const base = `${h}deg ${s}% ${l}%`;
  const opacities = [100, 60, 50, 40, 30, 20, 10];
  const keys = ["", "-60", "-50", "-40", "-30", "-20", "-10"];

  return opacities.reduce<GlowStyle>((vars, opacity, index) => {
    vars[`--glow-color${keys[index]}`] =
      `hsl(${base} / ${Math.min(opacity * intensity, 100)}%)`;
    return vars;
  }, {});
}

function buildGradientVars(colors: string[]): GlowStyle {
  const safeColors = colors.length > 0 ? colors : ["#2554d8"];
  const vars = gradientKeys.reduce<GlowStyle>((currentVars, key, index) => {
    const colorIndex = Math.min(colorMap[index], safeColors.length - 1);
    currentVars[key] =
      `radial-gradient(at ${gradientPositions[index]}, ${safeColors[colorIndex]} 0px, transparent 50%)`;
    return currentVars;
  }, {});

  vars["--gradient-base"] = `linear-gradient(${safeColors[0]} 0 100%)`;
  return vars;
}

function easeOutCubic(value: number) {
  return 1 - Math.pow(1 - value, 3);
}

function easeInCubic(value: number) {
  return value * value * value;
}

function animateValue({
  start = 0,
  end = 100,
  duration = 1000,
  delay = 0,
  ease = easeOutCubic,
  onUpdate,
  onEnd,
}: {
  start?: number;
  end?: number;
  duration?: number;
  delay?: number;
  ease?: (value: number) => number;
  onUpdate: (value: number) => void;
  onEnd?: () => void;
}) {
  const startTime = performance.now() + delay;

  function tick() {
    const elapsed = performance.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);
    onUpdate(start + (end - start) * ease(progress));

    if (progress < 1) {
      requestAnimationFrame(tick);
    } else {
      onEnd?.();
    }
  }

  setTimeout(() => requestAnimationFrame(tick), delay);
}

export default function BorderGlow({
  children,
  className = "",
  edgeSensitivity = 30,
  glowColor = "40 80 80",
  backgroundColor = "#ffffff",
  borderRadius = 8,
  glowRadius = 28,
  glowIntensity = 1,
  coneSpread = 25,
  animated = false,
  colors = ["#2554d8", "#1f7a3a", "#38bdf8"],
  fillOpacity = 0.28,
}: BorderGlowProps) {
  const cardRef = useRef<HTMLDivElement | null>(null);

  const getCenterOfElement = useCallback((element: HTMLDivElement) => {
    const { width, height } = element.getBoundingClientRect();
    return [width / 2, height / 2];
  }, []);

  const getEdgeProximity = useCallback(
    (element: HTMLDivElement, x: number, y: number) => {
      const [centerX, centerY] = getCenterOfElement(element);
      const dx = x - centerX;
      const dy = y - centerY;
      const kx = dx === 0 ? Infinity : centerX / Math.abs(dx);
      const ky = dy === 0 ? Infinity : centerY / Math.abs(dy);

      return Math.min(Math.max(1 / Math.min(kx, ky), 0), 1);
    },
    [getCenterOfElement],
  );

  const getCursorAngle = useCallback(
    (element: HTMLDivElement, x: number, y: number) => {
      const [centerX, centerY] = getCenterOfElement(element);
      const dx = x - centerX;
      const dy = y - centerY;

      if (dx === 0 && dy === 0) {
        return 0;
      }

      const radians = Math.atan2(dy, dx);
      const degrees = radians * (180 / Math.PI) + 90;
      return degrees < 0 ? degrees + 360 : degrees;
    },
    [getCenterOfElement],
  );

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const card = cardRef.current;
      if (!card) return;

      const rect = card.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const edge = getEdgeProximity(card, x, y);
      const angle = getCursorAngle(card, x, y);

      card.style.setProperty("--edge-proximity", `${(edge * 100).toFixed(3)}`);
      card.style.setProperty("--cursor-angle", `${angle.toFixed(3)}deg`);
    },
    [getCursorAngle, getEdgeProximity],
  );

  useEffect(() => {
    const card = cardRef.current;
    if (!animated || !card) return;

    const angleStart = 110;
    const angleEnd = 465;
    card.classList.add("sweep-active");
    card.style.setProperty("--cursor-angle", `${angleStart}deg`);

    animateValue({
      duration: 500,
      onUpdate: (value) => card.style.setProperty("--edge-proximity", `${value}`),
    });
    animateValue({
      ease: easeInCubic,
      duration: 1500,
      end: 50,
      onUpdate: (value) => {
        card.style.setProperty(
          "--cursor-angle",
          `${(angleEnd - angleStart) * (value / 100) + angleStart}deg`,
        );
      },
    });
    animateValue({
      ease: easeOutCubic,
      delay: 1500,
      duration: 2250,
      start: 50,
      end: 100,
      onUpdate: (value) => {
        card.style.setProperty(
          "--cursor-angle",
          `${(angleEnd - angleStart) * (value / 100) + angleStart}deg`,
        );
      },
    });
    animateValue({
      ease: easeInCubic,
      delay: 2500,
      duration: 1500,
      start: 100,
      end: 0,
      onUpdate: (value) => card.style.setProperty("--edge-proximity", `${value}`),
      onEnd: () => card.classList.remove("sweep-active"),
    });
  }, [animated]);

  const style: GlowStyle = {
    "--card-bg": backgroundColor,
    "--edge-sensitivity": edgeSensitivity,
    "--border-radius": `${borderRadius}px`,
    "--glow-padding": `${glowRadius}px`,
    "--cone-spread": coneSpread,
    "--fill-opacity": fillOpacity,
    ...buildGlowVars(glowColor, glowIntensity),
    ...buildGradientVars(colors),
  };

  return (
    <div
      ref={cardRef}
      className={`border-glow-card ${className}`.trim()}
      onPointerMove={handlePointerMove}
      style={style}
    >
      <span className="edge-light" />
      <div className="border-glow-inner">{children}</div>
    </div>
  );
}
