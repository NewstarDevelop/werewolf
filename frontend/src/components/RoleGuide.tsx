import { useState } from "react";

import { roleGuides } from "../copy";

interface RoleGuideProps {
  roleCode?: string;
}

/**
 * Folded panel under the identity card. Shows the user's role abilities so
 * first-time players don't have to memorise werewolf rules before acting.
 */
export function RoleGuide({ roleCode }: RoleGuideProps) {
  const [open, setOpen] = useState(false);
  const guide = roleCode ? roleGuides[roleCode] : undefined;

  if (!guide) return null;

  return (
    <details
      className={`role-guide role-guide--${guide.camp}`}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="role-guide__summary">
        <span className="role-guide__label">{guide.name}技能</span>
        <span className="role-guide__chevron" aria-hidden="true">
          {open ? "收起" : "展开"}
        </span>
      </summary>
      <p className="role-guide__one-liner">{guide.oneLiner}</p>
      <ul className="role-guide__abilities">
        {guide.abilities.map((ability) => (
          <li key={ability}>{ability}</li>
        ))}
      </ul>
    </details>
  );
}
