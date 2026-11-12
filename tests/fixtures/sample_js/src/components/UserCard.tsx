/** Renders one user. */
import React from "react";
import { normalize } from "../utils";
import type User from "../models";
import "./card.css";

/** Card showing a user's label. */
export default function UserCard({ user }: { user: User }) {
  const title = normalize(user.label());
  return (
    <div className="card">
      <Badge text={title} />
    </div>
  );
}

function Badge({ text }: { text: string }) {
  return <span>{text}</span>;
}
