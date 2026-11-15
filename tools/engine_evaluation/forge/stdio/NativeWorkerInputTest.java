// SPDX-License-Identifier: GPL-3.0-or-later
// Original JSON transport checks beside the Forge Team/Card-Forge integration.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import java.util.List;
import java.io.PrintWriter;
import java.io.StringWriter;
import forge.gamemodes.net.ProtocolMethod;
import forge.gamemodes.net.event.GuiGameEvent;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class NativeWorkerInputTest {
    private static final String ID = "12345678-1234-1234-1234-123456789abc";

    @DataProvider(name="valid")
    public Object[][] valid() {
        return new Object[][] {
            {"{\"request_id\":\""+ID+"\",\"tokens\":[\""+ID+"\"]}", List.of(ID)},
            {"{\"tokens\":[],\"request_id\":\""+ID+"\"}", List.of()}
        };
    }

    @DataProvider(name="invalid")
    public Object[][] invalid() {
        String prefix="{\"request_id\":\""+ID+"\",\"tokens\":[]";
        return new Object[][] {
            {prefix+",\"actor_id\":0}"},
            {prefix+",\"request_id\":\""+ID+"\"}"},
            {prefix+",\"tokens\":[]}"},
            {"{\"request_id\":3,\"tokens\":[]}"},
            {"{\"request_id\":null,\"tokens\":[]}"},
            {"{\"request_id\":\"\",\"tokens\":[]}"},
            {"{\"request_id\":\""+ID+"\",\"tokens\":[3]}"},
            {"{\"request_id\":\""+ID+"\",\"tokens\":[null]}"},
            {"{\"request_id\":\""+ID+"\",\"tokens\":[\""+ID+"\",\""+ID+"\"]}"},
            {prefix+"} {}"},
            {"{request_id:'"+ID+"',tokens:[]}"},
            {"{\"request_id\":\""+ID+"\",\"tokens\":[]"},
            {" ".repeat(16_385)+prefix+"}"}
        };
    }

    @Test(dataProvider="valid")
    public void acceptsOnlyTheTwoDocumentedReplyFields(String json,List<String> tokens) {
        NativeHumanWorker.Answer answer=NativeHumanWorker.decode(json);
        Assert.assertEquals(answer.request(),ID);
        Assert.assertEquals(answer.tokens(),tokens);
    }

    @Test(dataProvider="invalid")
    public void rejectsAmbiguousOrActorSelectingReplies(String json) {
        Assert.expectThrows(IllegalArgumentException.class,() -> NativeHumanWorker.decode(json));
    }

    @DataProvider(name="bounds")
    public Object[][] bounds() {
        return new Object[][] {{-1,-1,1,0,0}, {0,999,2,0,2}, {1,-1,2,1,2}};
    }

    @Test(dataProvider="bounds")
    public void nativeRevealRequiresAcknowledgmentNotASelection(int min,int max,int count,int expectedMin,int expectedMax) {
        Assert.assertEquals(NativeHumanWorker.choiceBounds(min,max,count),new int[] {expectedMin,expectedMax});
    }

    @Test
    public void clickingASourceWithNoAvailableAbilityReturnsNoAction() {
        NativeHumanWorker worker = new NativeHumanWorker(new PrintWriter(new StringWriter()));
        Assert.assertNull(worker.sendAndWait(new GuiGameEvent(ProtocolMethod.getAbilityToPlay,null,List.of(),null)));
    }

    @DataProvider(name="questions")
    public Object[][] questions() {
        return new Object[][] {
            {new GuiGameEvent(ProtocolMethod.confirm,null,"Pay the optional cost?",true,List.of("Pay","Decline")),"Pay the optional cost?"},
            {new GuiGameEvent(ProtocolMethod.showConfirmDialog,"Draw a card?","Optional draw","Yes","No",true),"Draw a card?"},
            {new GuiGameEvent(ProtocolMethod.getChoices,"Choose a mode",1,1,List.of("A","B"),List.of(),null),"Choose a mode"}
        };
    }

    @Test(dataProvider="questions")
    public void explicitNativeQuestionAccompaniesItsChoices(GuiGameEvent call,String prompt) {
        Assert.assertEquals(NativeHumanWorker.dialogInfo(call).get("prompt"),prompt);
    }

    @Test
    public void queuedDispatchFailureCannotLeaveTheWorkerWaiting() throws Exception {
        NativeHumanWorker worker = new NativeHumanWorker(new PrintWriter(new StringWriter()));
        worker.dispatch(() -> { throw new IllegalStateException("internal protocol failure"); });
        var failed = NativeHumanWorker.class.getDeclaredField("failed");
        failed.setAccessible(true);
        Assert.assertTrue(failed.getBoolean(worker));
    }

    @DataProvider(name="orders")
    public Object[][] orders() {
        return new Object[][] {{List.of("A","B"),List.of()}, {List.of(),List.of("A","B")}};
    }

    @Test(dataProvider="orders")
    public void nativeMandatoryOrderRetainsEveryChoiceForClientPermutation(List<?> source,List<?> destination) {
        GuiGameEvent event = new GuiGameEvent(ProtocolMethod.order,"Order triggers","Resolve first",0,0,source,destination,null,false,true);
        Assert.assertEquals(NativeHumanWorker.orderChoices(event),List.of("A","B"));
    }

    @Test
    public void protocolAbortIgnoresALateCompletionCallback() {
        StringWriter output = new StringWriter();
        NativeHumanWorker worker = new NativeHumanWorker(new PrintWriter(output));
        worker.abort();
        worker.completed(null); // No game access is allowed after the actor connection closed.
        Assert.assertEquals(output.toString().lines().count(),1L);
        Assert.assertTrue(output.toString().contains("\"event\":\"aborted\""));
    }
}
