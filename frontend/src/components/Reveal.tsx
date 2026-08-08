// Enter/exit animation wrapper, no dependency. React unmounts instantly, so to
// animate an exit we keep the node mounted until the fade-out animation ends.
import { ReactNode, useEffect, useState } from "react";

export default function Reveal({
  show,
  children,
  className = "",
}: {
  show: boolean;
  children: ReactNode;
  className?: string;
}) {
  const [render, setRender] = useState(show);
  useEffect(() => {
    if (show) setRender(true);
  }, [show]);
  if (!render) return null;
  return (
    <div
      className={`${className} ${show ? "reveal-in" : "reveal-out"}`}
      onAnimationEnd={() => {
        if (!show) setRender(false);
      }}
    >
      {children}
    </div>
  );
}
