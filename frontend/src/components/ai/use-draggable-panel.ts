"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, PointerEventHandler } from "react";

const DESKTOP_MEDIA_QUERY = "(min-width: 1024px)";
const VIEWPORT_MARGIN = 16;

type Point = {
  x: number;
  y: number;
};

type Size = {
  width: number;
  height: number;
};

type DragSession = {
  pointerId: number;
  offsetX: number;
  offsetY: number;
};

type PanelStyle = CSSProperties & {
  "--panel-left"?: string;
  "--panel-top"?: string;
};

export function clampPanelPosition(
  position: Point,
  panel: Size,
  viewport: Size,
  margin = VIEWPORT_MARGIN
): Point {
  const maxX = Math.max(margin, viewport.width - panel.width - margin);
  const maxY = Math.max(margin, viewport.height - panel.height - margin);

  return {
    x: Math.min(Math.max(position.x, margin), maxX),
    y: Math.min(Math.max(position.y, margin), maxY),
  };
}

export function useDraggablePanel() {
  const panelRef = useRef<HTMLElement>(null);
  const dragSessionRef = useRef<DragSession | null>(null);
  const [position, setPosition] = useState<Point | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const constrainPosition = useCallback((nextPosition: Point): Point => {
    const panel = panelRef.current;
    if (!panel) return nextPosition;

    const bounds = panel.getBoundingClientRect();
    return clampPanelPosition(
      nextPosition,
      { width: bounds.width, height: bounds.height },
      { width: window.innerWidth, height: window.innerHeight }
    );
  }, []);

  const onPointerDown: PointerEventHandler<HTMLElement> = useCallback((event) => {
    if (event.button !== 0 || !window.matchMedia(DESKTOP_MEDIA_QUERY).matches) return;

    const target = event.target;
    if (target instanceof Element && target.closest("button")) return;

    const panel = panelRef.current;
    if (!panel) return;

    const bounds = panel.getBoundingClientRect();
    dragSessionRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - bounds.left,
      offsetY: event.clientY - bounds.top,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setPosition({ x: bounds.left, y: bounds.top });
    setIsDragging(true);
    event.preventDefault();
  }, []);

  const onPointerMove: PointerEventHandler<HTMLElement> = useCallback(
    (event) => {
      const dragSession = dragSessionRef.current;
      if (!dragSession || dragSession.pointerId !== event.pointerId) return;

      setPosition(
        constrainPosition({
          x: event.clientX - dragSession.offsetX,
          y: event.clientY - dragSession.offsetY,
        })
      );
    },
    [constrainPosition]
  );

  const endDrag: PointerEventHandler<HTMLElement> = useCallback((event) => {
    const dragSession = dragSessionRef.current;
    if (!dragSession || dragSession.pointerId !== event.pointerId) return;

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragSessionRef.current = null;
    setIsDragging(false);
  }, []);

  useEffect(() => {
    const stopDragging = () => {
      dragSessionRef.current = null;
      setIsDragging(false);
    };
    const keepPanelInViewport = () => {
      stopDragging();
      if (!window.matchMedia(DESKTOP_MEDIA_QUERY).matches) return;
      setPosition((current) => (current ? constrainPosition(current) : current));
    };

    window.addEventListener("blur", stopDragging);
    window.addEventListener("resize", keepPanelInViewport);
    return () => {
      window.removeEventListener("blur", stopDragging);
      window.removeEventListener("resize", keepPanelInViewport);
    };
  }, [constrainPosition]);

  const panelStyle: PanelStyle | undefined = position
    ? {
        "--panel-left": `${position.x}px`,
        "--panel-top": `${position.y}px`,
      }
    : undefined;

  return {
    panelRef,
    panelStyle,
    panelPositioned: position !== null,
    isDragging,
    dragHandleProps: {
      onPointerDown,
      onPointerMove,
      onPointerUp: endDrag,
      onPointerCancel: endDrag,
    },
  };
}
