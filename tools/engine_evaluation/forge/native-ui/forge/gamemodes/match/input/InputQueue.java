/*
 * Forge: Play Magic: the Gathering.
 * Copyright (C) 2011  Forge Team
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
package forge.gamemodes.match.input;

// Owned 2026-11-05 patch on Forge 61e9442: optional generation-bound presentation ABI.
// Owned correction: same-input normal-return interaction receipts reuse that ABI.
// Owned R7 observation only: report successful popped object/generations outside monitor.

import forge.game.GameView;
import forge.util.IHasForgeLog;
import forge.player.PlayerControllerHuman;

import java.util.Observable;
import java.util.concurrent.BlockingDeque;
import java.util.concurrent.LinkedBlockingDeque;

/**
 * <p>
 * InputControl class.
 * </p>
 *
 * @author Forge
 * @version $Id: InputQueue.java 24769 2014-02-09 13:56:04Z Hellfish $
 */
public class InputQueue extends Observable implements IHasForgeLog {

    private final BlockingDeque<InputSynchronized> inputStack = new LinkedBlockingDeque<>();
    private final GameView gameView;
    private long inputGeneration;
    private boolean presentationEnded;
    private volatile PresentationListener presentationListener;
    private record PresentationContext(Input input, long generation) { }
    private final ThreadLocal<PresentationContext> presenting = new ThreadLocal<>();
    public interface RemovalObserver {
        void removed(Input input, long beforeGeneration, long afterGeneration);
    }
    private volatile RemovalObserver removalObserver;
    public final void setRemovalObserver(final RemovalObserver observer) {
        removalObserver = observer;
    }

    public interface PresentationListener {
        void invalidated();
        void presented(Input input, long generation);
    }

    public final void setPresentationListener(final PresentationListener listener) {
        synchronized (this) {
            presentationListener = listener;
            inputChanged();
        }
        notifyInvalidated();
    }

    public final boolean hasPresentationListener() {
        return presentationListener != null;
    }

    public final synchronized long getInputGeneration() {
        return inputGeneration;
    }

    public final synchronized boolean isCurrentPresentation(final Input input, final long generation) {
        return input != null && !presentationEnded && !gameView.isGameOver()
                && inputGeneration == generation && inputStack.peek() == input;
    }

    // Call with the queue monitor; never call host code while holding it.
    private void inputChanged() {
        inputGeneration++;
    }

    private void notifyInvalidated() {
        final PresentationListener listener = presentationListener;
        if (listener != null) listener.invalidated();
    }

    final void presentInput(final Input input, final long generation) {
        if (!isCurrentPresentation(input, generation)) return;
        final PresentationContext previous = presenting.get();
        presenting.set(new PresentationContext(input, generation));
        try {
            input.showMessageInitial();
        } finally {
            if (previous == null) presenting.remove();
            else presenting.set(previous);
        }
    }

    final void presentationCompleted(final Input input) {
        final PresentationContext context = presenting.get();
        final PresentationListener listener = presentationListener;
        if (listener != null && context != null && context.input() == input
                && isCurrentPresentation(input, context.generation())) {
            listener.presented(input, context.generation());
        }
    }

    final void interactionCompleted(final Input input, final long generation) {
        // Initial presentation owns its later full-completion receipt.
        if (presenting.get() != null) return;
        final PresentationListener listener = presentationListener;
        if (listener != null && isCurrentPresentation(input, generation)) {
            listener.presented(input, generation);
        }
    }

    public InputQueue(final GameView gameView, final InputProxy inputProxy) {
        this.gameView = gameView;
        addObserver(inputProxy);
    }

    public final void updateObservers() {
        setChanged();
        notifyObservers();
    }

    public final Input getInput() {
        return inputStack.isEmpty() ? null : inputStack.peek();
    }

    /*pfps sometimes this is being called twice for the same input */
    public final void removeInput(final Input inp) {
        boolean popped = false;
        final long beforeGeneration, afterGeneration;
        synchronized (this) {
        beforeGeneration = inputGeneration;
        final Input topMostInput = inputStack.isEmpty() ? null : inputStack.peek();

        if (topMostInput != inp) {
            System.out.println("Cannot remove input " + inp.getClass().getSimpleName() + " because it's not on top of stack. Stack = " + inputStack );
        } else if (topMostInput != null) {
            // if topMostInput is null then it means the inputstack is already empty, why this is called twice?
           inputStack.pop();
           popped = true;
        }
        inputChanged();
        afterGeneration = inputGeneration;
        }
        notifyInvalidated();
        final RemovalObserver observer = removalObserver;
        if (popped && observer != null) observer.removed(inp, beforeGeneration, afterGeneration);
        updateObservers();
    }

    public final void clearInputs() {
        netLog.trace("clearInputs() called, stack size = {}", inputStack.size());
        int count = 0;
        while(!inputStack.isEmpty()) {
            final InputSynchronized inp;
            synchronized (this) {
                inp = inputStack.poll();
                if (inp == null) break;
                inputChanged();
            }
            notifyInvalidated();
            netLog.trace("Stopping input #{}: {}", count, inp.getClass().getSimpleName());
            inp.stop();
            count++;
        }
        netLog.trace("clearInputs() done, stopped {} inputs", count);

        updateObservers();
    }

    public final Input getActualInput(final PlayerControllerHuman controller) {
        final Input topMost = inputStack.peek(); // incoming input to Control
        if (topMost != null && !gameView.isGameOver()) {
            return topMost;
        }
        return new InputLockUI(this, controller);
    } // getInput()

    // only for debug purposes
    public String printInputStack() {
        return inputStack.toString();
    }

    public void setInput(final InputSynchronized input) {
        //if (HostedMatch.getHumanCount() > 1) { //update current player if needed
            //HostedMatch.setCurrentPlayer(game.getPlayer(input.getOwner()));
        //}
        synchronized (this) {
            inputStack.push(input);
            inputChanged();
        }
        notifyInvalidated();
        // onGameOver releases only the inputs already waiting when it runs
        if (gameView.isGameOver()) {
            input.relaseLatchWhenGameIsOver();
        }
        syncPoint();
        updateObservers();
    }

    void syncPoint() {
        synchronized (this) {
            // acquire and release lock, so that actions from Game thread happen before EDT reads their results
        }
    }

    public void onGameOver(final boolean releaseAllInputs) {
        synchronized (this) {
            presentationEnded = true;
            inputChanged();
        }
        notifyInvalidated();
        for (final InputSynchronized inp : inputStack) {
            inp.relaseLatchWhenGameIsOver();
            if (!releaseAllInputs) {
                break;
            }
        }
    }
}
