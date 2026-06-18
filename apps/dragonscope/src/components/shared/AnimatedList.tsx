import { memo, type ReactElement, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { listContainerVariants, listItemVariants } from '../../utils/motion';

interface AnimatedListProps {
  children: ReactNode;
  className?: string;
}

const AnimatedList = memo(({ children, className }: AnimatedListProps): ReactElement => {
  return (
    <motion.div
      className={className}
      variants={listContainerVariants}
      initial="hidden"
      animate="visible"
    >
      <AnimatePresence mode="popLayout">
        {children}
      </AnimatePresence>
    </motion.div>
  );
});
AnimatedList.displayName = 'AnimatedList';

interface AnimatedListItemProps {
  children: ReactNode;
  layoutId?: string;
  className?: string;
}

export const AnimatedListItem = memo(({ children, layoutId, className }: AnimatedListItemProps): ReactElement => {
  return (
    <motion.div
      layout
      layoutId={layoutId}
      variants={listItemVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className={className}
    >
      {children}
    </motion.div>
  );
});
AnimatedListItem.displayName = 'AnimatedListItem';

export default AnimatedList;
