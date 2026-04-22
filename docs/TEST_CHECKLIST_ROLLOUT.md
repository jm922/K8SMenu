# TEST_CHECKLIST_ROLLOUT

## Purpose

This document is used to test and validate the **Rollout Status** feature in the Kubernetes Resource Manager Deployment module.

The purpose of this checklist is to verify that the rollout status workflow works correctly, clearly, and safely in normal, edge, and failure scenarios.

---

## Feature Under Test

Menu path:

```text
Deployment -> Rollout Status
```

Expected high-level behavior:

1. List available Deployments
2. Select a Deployment by number or name
3. Accept a timeout value
4. Show the exact `kubectl rollout status` command before execution
5. Ask for user confirmation
6. Execute the rollout status command
7. Show kubectl output
8. Show current Deployment status summary

---

## Recommended Test Deployment

Recommended Deployment name for testing:

```text
quicktest-web
```

Recommended reasons:

- already exists in the current test flow
- simple nginx workload
- easy to scale
- rollout behavior is easy to observe

---

## Environment Baseline Check

### Objective
Make sure the cluster and Deployment environment are healthy enough to run rollout status tests.

### Steps
- [ ] Run `kubectl get nodes`
- [ ] Run `kubectl get deployment`
- [ ] Confirm at least one Deployment exists
- [ ] Confirm the target Deployment is accessible

### Reference Commands

```bash
kubectl get nodes
kubectl get deployment
kubectl get deployment quicktest-web
```

### Expected Result
- [ ] `kubectl` works normally
- [ ] nodes are in `Ready` state
- [ ] target Deployment exists
- [ ] no obvious cluster-side failure blocks testing

### Result Notes
- Result:
- Notes:

---

## Test Case 01 - Stable Deployment by Name

### Objective
Verify rollout status works correctly when a stable Deployment is selected by name.

### Preconditions
- [ ] Cluster is healthy
- [ ] Deployment `quicktest-web` exists
- [ ] Deployment is already stable

### Steps
- [ ] Open `Deployment -> Rollout Status`
- [ ] Enter deployment name: `quicktest-web`
- [ ] Press Enter to accept default timeout `60s`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] The full kubectl command is displayed before execution
- [ ] The command is shown as:
  ```bash
  kubectl rollout status deployment/quicktest-web --timeout=60s
  ```
- [ ] The rollout check runs successfully
- [ ] Success output is displayed
- [ ] A Deployment status summary is displayed after the command

### Reference Command

```bash
kubectl rollout status deployment/quicktest-web --timeout=60s
```

### Result Notes
- Result:
- Notes:

---

## Test Case 02 - Stable Deployment by Number

### Objective
Verify rollout status works correctly when a stable Deployment is selected by menu number.

### Preconditions
- [ ] At least one Deployment exists in the current namespace
- [ ] The selected Deployment is stable

### Steps
- [ ] Open `Deployment -> Rollout Status`
- [ ] Enter the deployment number shown in the menu list
- [ ] Press Enter to accept default timeout `60s`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] Deployment number is resolved correctly
- [ ] No `Deployment not found` error
- [ ] Rollout check runs successfully
- [ ] Success output is displayed
- [ ] Deployment status summary is displayed

### Reference Command

```bash
kubectl rollout status deployment/quicktest-web --timeout=60s
```

### Result Notes
- Result:
- Notes:

---

## Test Case 03 - Default Timeout

### Objective
Verify that the default timeout is correctly applied when the timeout input is left empty.

### Preconditions
- [ ] A valid Deployment exists
- [ ] Rollout Status menu is reachable

### Steps
- [ ] Open `Deployment -> Rollout Status`
- [ ] Select a valid Deployment
- [ ] Press Enter without typing a timeout value
- [ ] Confirm execution with `y`

### Expected Result
- [ ] Timeout defaults to `60s`
- [ ] The command preview includes `--timeout=60s`
- [ ] The command executes normally

### Reference Command

```bash
kubectl rollout status deployment/quicktest-web --timeout=60s
```

### Result Notes
- Result:
- Notes:

---

## Test Case 04 - Custom Timeout

### Objective
Verify that a custom timeout value is accepted and shown correctly in the command preview.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Open `Deployment -> Rollout Status`
- [ ] Select a valid Deployment
- [ ] Enter timeout: `15s`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] The command preview includes `--timeout=15s`
- [ ] The command executes normally
- [ ] Output is displayed normally

### Reference Command

```bash
kubectl rollout status deployment/quicktest-web --timeout=15s
```

### Result Notes
- Result:
- Notes:

---

## Test Case 05 - Cancel Flow

### Objective
Verify that the rollout status operation can be cancelled before execution.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Open `Deployment -> Rollout Status`
- [ ] Select a valid Deployment
- [ ] Enter a timeout value or accept default
- [ ] At the confirmation prompt, enter `n`

### Expected Result
- [ ] The full kubectl command is displayed before cancellation
- [ ] A cancel message is displayed
- [ ] No rollout command is executed
- [ ] No traceback occurs
- [ ] Program returns safely to the menu flow

### Reference Command

```bash
# No kubectl rollout command should actually be executed in this test
```

### Result Notes
- Result:
- Notes:

---

## Test Case 06 - Non-Existent Deployment

### Objective
Verify that an invalid Deployment name is handled clearly and safely.

### Preconditions
- [ ] Rollout Status menu is reachable

### Steps
- [ ] Open `Deployment -> Rollout Status`
- [ ] Enter deployment name: `not-exist-deployment`

### Expected Result
- [ ] `Deployment not found` is displayed
- [ ] No rollout command is executed
- [ ] No traceback occurs
- [ ] Program returns safely

### Reference Command

```bash
# No kubectl rollout command should be executed because deployment does not exist
```

### Result Notes
- Result:
- Notes:

---

## Test Case 07 - Invalid Deployment Number

### Objective
Verify that an invalid deployment number is handled correctly.

### Preconditions
- [ ] There is at least one Deployment in the menu list

### Steps
- [ ] Open `Deployment -> Rollout Status`
- [ ] Enter an invalid number such as `99`

### Expected Result
- [ ] `Deployment not found` is displayed
- [ ] No rollout command is executed
- [ ] No traceback occurs
- [ ] Program returns safely

### Result Notes
- Result:
- Notes:

---

## Test Case 08 - Rollout In Progress After Scale Up

### Objective
Verify rollout status works correctly while a Deployment is actively changing.

### Preconditions
- [ ] Deployment `quicktest-web` exists
- [ ] Scale feature is working

### Steps
- [ ] Scale `quicktest-web` from `1` to `3`
- [ ] Immediately open `Deployment -> Rollout Status`
- [ ] Select `quicktest-web`
- [ ] Use timeout `60s`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] Rollout status waits while the Deployment is progressing
- [ ] Final output shows rollout success
- [ ] Final Deployment status summary shows the target state
- [ ] Pod count eventually matches desired replicas

### Reference Commands

```bash
kubectl scale deployment quicktest-web --replicas=3
kubectl rollout status deployment/quicktest-web --timeout=60s
kubectl get deployment quicktest-web
kubectl get pods -l app=quicktest-web -o wide
```

### Result Notes
- Result:
- Notes:

---

## Test Case 09 - Rollout In Progress After Scale Down

### Objective
Verify rollout status also behaves correctly during scale down.

### Preconditions
- [ ] Deployment `quicktest-web` exists
- [ ] Deployment currently has more than 1 replica

### Steps
- [ ] Scale `quicktest-web` from `3` to `1`
- [ ] Immediately open `Deployment -> Rollout Status`
- [ ] Select `quicktest-web`
- [ ] Use timeout `60s`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] Rollout status waits while extra Pods are terminated
- [ ] Final output shows rollout success
- [ ] Final Deployment status summary reflects desired replica count = 1

### Reference Commands

```bash
kubectl scale deployment quicktest-web --replicas=1
kubectl rollout status deployment/quicktest-web --timeout=60s
kubectl get deployment quicktest-web
kubectl get pods -l app=quicktest-web -o wide
```

### Result Notes
- Result:
- Notes:

---

## Test Case 10 - Short Timeout

### Objective
Verify timeout handling with a very short timeout value.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Open `Deployment -> Rollout Status`
- [ ] Select a valid Deployment
- [ ] Enter timeout: `1s`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] Either rollout succeeds immediately or a timeout/failure message is shown
- [ ] Failure/timeout output is readable
- [ ] No traceback occurs

### Reference Command

```bash
kubectl rollout status deployment/quicktest-web --timeout=1s
```

### Result Notes
- Result:
- Notes:

---

## Test Case 11 - Timeout Formatting

### Objective
Verify timeout-related output formatting is readable and clear.

### Preconditions
- [ ] A short timeout test has been executed

### Steps
- [ ] Trigger a timeout or failure case
- [ ] Review the output shown by the menu tool

### Expected Result
- [ ] Error message is clearly visible
- [ ] kubectl stdout/stderr is displayed when available
- [ ] Formatting remains readable
- [ ] No broken line structure or confusing output blocks

### Result Notes
- Result:
- Notes:

---

## Test Case 12 - Command Preview Accuracy

### Objective
Verify the displayed kubectl command exactly matches the intended command.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Run `Deployment -> Rollout Status`
- [ ] Record the previewed kubectl command
- [ ] Manually run the same command in terminal
- [ ] Compare outputs

### Expected Result
- [ ] Command preview is accurate
- [ ] Manual command output matches menu command output
- [ ] No mismatch between displayed command and executed behavior

### Reference Command

```bash
kubectl rollout status deployment/quicktest-web --timeout=60s
```

### Result Notes
- Result:
- Notes:

---

## Test Case 13 - Output Readability

### Objective
Verify the output formatting is easy to read.

### Preconditions
- [ ] Rollout Status feature works at least in one successful scenario

### Steps
- [ ] Run one successful rollout status test
- [ ] Review the output carefully

### Expected Result
- [ ] Title is clearly separated
- [ ] Deployment name is easy to identify
- [ ] Timeout is clearly shown
- [ ] kubectl command is displayed on its own line
- [ ] Success output is visually easy to notice
- [ ] Failure output is visually easy to notice
- [ ] Current Deployment status summary is readable
- [ ] Line breaks and spacing are reasonable

### Result Notes
- Result:
- Notes:

---

## Test Case 14 - Empty Deployment List

### Objective
Verify the feature behaves safely when no Deployment exists.

### Preconditions
- [ ] Current namespace has no Deployment

### Steps
- [ ] Open `Deployment -> Rollout Status`

### Expected Result
- [ ] `No deployments available` is shown
- [ ] No traceback occurs
- [ ] Program returns safely

### Reference Command

```bash
kubectl get deployment
```

### Result Notes
- Result:
- Notes:

---

## Test Case 15 - Mixed Number and Name Validation

### Objective
Verify that both number-based and name-based selection remain stable across repeated tests.

### Preconditions
- [ ] At least one Deployment exists

### Steps
- [ ] Run rollout status once using deployment number
- [ ] Run rollout status again using deployment name
- [ ] Compare behavior

### Expected Result
- [ ] Both selection methods work consistently
- [ ] No unexpected parsing issue occurs
- [ ] Output structure remains consistent

### Result Notes
- Result:
- Notes:

---

## Test Case 16 - Repeated Execution Stability

### Objective
Verify the feature works repeatedly without drifting into inconsistent behavior.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Run rollout status 3 times in a row on the same stable Deployment
- [ ] Use a mix of default and custom timeout values

### Expected Result
- [ ] No crash occurs
- [ ] No inconsistent output appears
- [ ] Command preview remains correct every time

### Result Notes
- Result:
- Notes:

---

## Test Case 17 - After Deployment Update Scenario

### Objective
Prepare a template for future testing after image update is implemented.

### Preconditions
- [ ] Update Image feature exists
- [ ] Deployment image can be changed

### Steps
- [ ] Update deployment image
- [ ] Immediately run `Deployment -> Rollout Status`
- [ ] Observe rollout behavior

### Expected Result
- [ ] Rollout waits until the new image rollout completes
- [ ] Final output shows success or failure clearly
- [ ] Final Deployment status summary reflects updated state

### Reference Commands

```bash
kubectl set image deployment/quicktest-web <container-name>=nginx:1.27
kubectl rollout status deployment/quicktest-web --timeout=60s
kubectl describe deployment quicktest-web
```

### Result Notes
- Result:
- Notes:

---

## Minimal Regression Checklist

Use this short section after any future change to rollout-related code.

- [ ] Stable rollout by deployment name
- [ ] Stable rollout by deployment number
- [ ] Default timeout
- [ ] Custom timeout
- [ ] Cancel flow
- [ ] Non-existent deployment
- [ ] Rollout in progress after scale up
- [ ] Short timeout
- [ ] Command preview accuracy
- [ ] Output readability

---

## Final Summary

### Overall Status
- [ ] All required rollout status tests passed
- [ ] Feature is ready for regular use
- [ ] Follow-up improvements are still needed

### Known Follow-Up Improvements
- [ ] Add shortcut to rollout status after scale
- [ ] Add shortcut to rollout status after image update
- [ ] Add namespace support
- [ ] Improve timeout validation
- [ ] Improve failure output formatting
- [ ] Support more guided troubleshooting messages

---

## Usage Notes

Recommended workflow:

1. Run one test case
2. Mark completed checkboxes with `- [x]`
3. Record the result in the `Result Notes` section
4. Keep this file updated as the feature evolves

Example:

```md
- [x] Stable rollout status by deployment name
```

Example result note:

```md
### Result Notes
- Result: Passed
- Notes: Output was correct and the command preview matched manual kubectl execution.
```
