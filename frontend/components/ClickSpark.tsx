"use client";

import { MouseEvent, ReactNode, useCallback, useEffect, useRef } from "react";

type Spark = {
  x: number;
  y: number;
  angle: number;
  startTime: number;
};

type ClickSparkProps = {
  sparkColor?: string;
  sparkSize?: number;
  sparkRadius?: number;
  sparkCount?: number;
  duration?: number;
  easing?: "linear" | "ease-in" | "ease-in-out" | "ease-out" | string;
  extraScale?: number;
  children: ReactNode;
};

export default function ClickSpark({
  sparkColor = "#fff",
  sparkSize = 10,
  sparkRadius = 15,
  sparkCount = 8,
  duration = 400,
  easing = "ease-out",
  extraScale = 1,
  children,
}: ClickSparkProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const sparksRef = useRef<Spark[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let resizeTimeout: ReturnType<typeof setTimeout>;

    const resizeCanvas = () => {
      const nextWidth = Math.max(1, Math.floor(window.innerWidth));
      const nextHeight = Math.max(1, Math.floor(window.innerHeight));

      if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
        canvas.width = nextWidth;
        canvas.height = nextHeight;
      }
    };

    const handleResize = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(resizeCanvas, 100);
    };

    window.addEventListener("resize", handleResize);
    resizeCanvas();

    return () => {
      window.removeEventListener("resize", handleResize);
      clearTimeout(resizeTimeout);
    };
  }, []);

  const easeFunc = useCallback(
    (progress: number) => {
      switch (easing) {
        case "linear":
          return progress;
        case "ease-in":
          return progress * progress;
        case "ease-in-out":
          return progress < 0.5
            ? 2 * progress * progress
            : -1 + (4 - 2 * progress) * progress;
        default:
          return progress * (2 - progress);
      }
    },
    [easing],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    let animationId: number;

    const draw = (timestamp: number) => {
      context.clearRect(0, 0, canvas.width, canvas.height);

      sparksRef.current = sparksRef.current.filter((spark) => {
        const elapsed = timestamp - spark.startTime;
        if (elapsed >= duration) {
          return false;
        }

        const progress = elapsed / duration;
        const eased = easeFunc(progress);
        const distance = eased * sparkRadius * extraScale;
        const lineLength = sparkSize * (1 - eased);
        const x1 = spark.x + distance * Math.cos(spark.angle);
        const y1 = spark.y + distance * Math.sin(spark.angle);
        const x2 = spark.x + (distance + lineLength) * Math.cos(spark.angle);
        const y2 = spark.y + (distance + lineLength) * Math.sin(spark.angle);

        context.strokeStyle = sparkColor;
        context.lineWidth = 2;
        context.beginPath();
        context.moveTo(x1, y1);
        context.lineTo(x2, y2);
        context.stroke();

        return true;
      });

      animationId = requestAnimationFrame(draw);
    };

    animationId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [duration, easeFunc, extraScale, sparkColor, sparkRadius, sparkSize]);

  function handleClick(event: MouseEvent<HTMLDivElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const now = performance.now();
    const sparks = Array.from({ length: sparkCount }, (_, index) => ({
      x,
      y,
      angle: (2 * Math.PI * index) / sparkCount,
      startTime: now,
    }));

    sparksRef.current.push(...sparks);
  }

  return (
    <div className="click-spark-root" onClick={handleClick}>
      <canvas ref={canvasRef} className="click-spark-canvas" />
      <div className="click-spark-content">{children}</div>
    </div>
  );
}
