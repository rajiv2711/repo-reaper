/** Entry point: renders a card per user. */
import { UserCard } from "./components";
import { UserService } from "./service";

const service = new UserService("/tmp/data");

/** Render one card per name. */
export function renderAll(names) {
  return names.map((name) => <UserCard key={name} user={service.create(name)} />);
}
