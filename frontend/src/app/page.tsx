import VideoInput from "../components/video_input";
import AuthButton from "../components/AuthButton";
import WorkflowList from "../components/WorkflowList";
import VideoHistory from "../components/VideoHistory";
import PendingWorkflows from "../components/PendingWorkflows";

export default function Home() {
  return (
    <div>
      <div className="p-4 flex justify-end">
        <AuthButton />
      </div>
      <PendingWorkflows />
      <VideoInput />
      <div className="p-8">
        <VideoHistory />
      </div>
      <WorkflowList />
    </div>
  )
}
