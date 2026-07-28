import { GroupBox } from "../ds/GroupBox";
import { People } from "./People";

/**
 * Admin app shell. There is exactly one screen -- the person who administers
 * the gateway sits down at the bench PC to manage access, not to navigate.
 */
export function App() {
  return (
    <div style={{ padding: "var(--space-4)", fontFamily: "var(--font-ui)", maxWidth: "960px", margin: "0 auto" }}>
      <GroupBox title="SCPI Gateway Admin">
        <People />
      </GroupBox>
    </div>
  );
}
