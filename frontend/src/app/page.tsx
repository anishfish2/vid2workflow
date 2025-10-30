import VideoInput from "../components/video_input";
import WorkflowBuilder from "../components/WorkflowBuilder";
import AuthButton from "../components/AuthButton";
import WorkflowList from "../components/WorkflowList";

export default function Home() {
  return (
    <div>
      <div className="p-4 flex justify-end">
        <AuthButton />
      </div>
      <VideoInput />
      <WorkflowBuilder />
      <WorkflowList />
    </div>
  )
}
