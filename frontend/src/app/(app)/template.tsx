"use client";

import { motion } from "motion/react";

/**
 * App Router template — re-mounts on every navigation, so this gives a consistent
 * page-transition animation across EVERY route (the header in layout.tsx stays put).
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
