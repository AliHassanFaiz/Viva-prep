import type { ReactNode, SVGProps } from "react";

const base = (children: ReactNode) => (props: SVGProps<SVGSVGElement>) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>
);

export const IconUpload = base(<><path d="M12 16V4" /><path d="m7 9 5-5 5 5" /><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></>);
export const IconFile = base(<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" /></>);
export const IconMic = base(<><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0" /><path d="M12 18v3" /></>);
export const IconStop = base(<rect x="6" y="6" width="12" height="12" rx="2" />);
export const IconPhoneOff = base(<><path d="M10.7 13.3a16 16 0 0 1-2.9-3.5l1.7-1.7a1.5 1.5 0 0 0 .3-1.6L8.8 4a1.5 1.5 0 0 0-1.7-.9L4.4 3.7A1.5 1.5 0 0 0 3.3 5.2 17 17 0 0 0 9 14.7" /><path d="M21 3 3 21" /></>);
export const IconCheck = base(<path d="m5 12 5 5 9-10" />);
export const IconX = base(<><path d="M6 6l12 12" /><path d="M18 6 6 18" /></>);
export const IconEdit = base(<><path d="M4 20h4L19 9a2.1 2.1 0 0 0-4-4L4 16z" /><path d="m14 6 4 4" /></>);
export const IconTrash = base(<><path d="M4 7h16" /><path d="M10 11v6M14 11v6" /><path d="M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12" /><path d="M9 7V4h6v3" /></>);
export const IconRefresh = base(<><path d="M20 11a8 8 0 0 0-14.5-4M4 4v4h4" /><path d="M4 13a8 8 0 0 0 14.5 4M20 20v-4h-4" /></>);
export const IconHeadphones = base(<><path d="M4 15v-3a8 8 0 0 1 16 0v3" /><rect x="3" y="14" width="4" height="6" rx="1.5" /><rect x="17" y="14" width="4" height="6" rx="1.5" /></>);
export const IconKeyboard = base(<><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10" /></>);
export const IconHistory = base(<><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><path d="M12 8v4l3 2" /></>);
export const IconSpark = base(<><path d="M12 3v4M12 17v4M3 12h4M17 12h4" /><path d="m6 6 2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" /></>);
export const IconShield = base(<><path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6z" /><path d="m9 12 2 2 4-4" /></>);
export const IconChevron = base(<path d="m9 6 6 6-6 6" />);
export const IconPlay = base(<path d="M7 5v14l12-7z" />);
