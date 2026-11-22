import { Registrations } from "./Weekly";
import { RegistrationsV2 } from "./WeeklyV2";
import episode from "./current-episode";

export const RemotionRoot: React.FC = () => {
  const template = (episode as unknown as { template?: string }).template;
  return template === "v2" ? <RegistrationsV2 /> : <Registrations />;
};
