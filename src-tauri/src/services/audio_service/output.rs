/// A completed dictation keeps the target captured when its recording began.
#[derive(Clone)]
pub(crate) struct PendingPaste {
    pub session_id: u64,
    pub target_window: Option<isize>,
    pub text: String,
}

impl PendingPaste {
    pub fn target_matches(&self, current_window: Option<isize>) -> bool {
        self.target_window.is_some() && self.target_window == current_window
    }
}

#[derive(Default)]
pub(crate) struct PendingPasteQueue {
    pending: Vec<PendingPaste>,
}

impl PendingPasteQueue {
    pub fn push(&mut self, output: PendingPaste) {
        if !self
            .pending
            .iter()
            .any(|item| item.session_id == output.session_id)
        {
            self.pending.push(output);
        }
    }

    pub fn take_if_idle(&mut self, recording: bool) -> Vec<PendingPaste> {
        if recording {
            Vec::new()
        } else {
            std::mem::take(&mut self.pending)
        }
    }
}
